from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from models.candidate import Candidate
from models.user_context import UserContext
from services import database
from services.admin_access_session import AdminAccessSession
from services.candidate_repository import CandidateRepository
from services.company_normalization import company_name
from services.company_repository import CompanyRepository
from services.company_source_repository import CompanySourceRepository
from services.monitored_company_repository import MonitoredCompanyRepository
from services.employer_provider_registry import build_employer_provider_configs, employer_run_name
from services.daily_ingestion_service import DailyIngestionService
from services.user_repository import UserRepository


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    import requests
    def forbidden(*a, **kw):
        pytest.fail("External network is forbidden.")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(params=["sqlite", "postgres_adapter_double"])
def db(request, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(database, "DATABASE_FILE", tmp_path / "companies.db")
    database.initialize_database.cache_clear()
    database.initialize_database()
    if request.param == "postgres_adapter_double":
        original = database.get_connection
        class Driver:
            def __init__(self, connection):
                self.connection = connection
            def execute(self, query, params=None):
                if params:
                    assert "?" not in query
                    assert "%s" in query
                return self.connection.execute(query.replace("%s", "?"), params or ())
        @contextmanager
        def adapted():
            with original() as connection:
                yield database.PostgresConnectionAdapter(Driver(connection))
        for module in (
            "services.company_repository", "services.company_source_repository",
            "services.monitored_company_repository",
        ):
            monkeypatch.setattr(module + ".get_connection", adapted)
    yield
    database.initialize_database.cache_clear()


@pytest.fixture
def users(db):
    result = []
    for identifier in ("a", "b", "admin"):
        CandidateRepository().save(Candidate(
            id=identifier, name=identifier, current_role="", current_level="",
            professional_summary="",
        ))
        result.append(UserRepository().create(
            identifier + "@example.test", identifier, candidate_id=identifier,
            user_id=identifier, access_level="admin" if identifier == "admin" else "user",
        ))
    return result


def watch(user, active=None, grant=None):
    return MonitoredCompanyRepository(UserContext(user, active or user), admin_access=grant)


def test_company_creation_and_global_duplicate(db):
    repository = CompanyRepository()
    first = repository.get_or_create_company("  Bank   of Ireland ", domain="EXAMPLE.IE")
    duplicate = repository.get_or_create_company("bank of ireland")
    assert first.id == duplicate.id
    assert first.canonical_name == "Bank of Ireland"
    assert first.normalized_name == "bank of ireland"
    assert first.domain == "example.ie"
    assert first.created_at == duplicate.created_at
    assert repository.find_company("BANK OF IRELAND") == first
    assert repository.get(first.id) == first
    assert repository.find_company("Absent") is None
    assert "candidate_id" not in asdict(first)


@pytest.mark.parametrize("left,right", [
    ("Meta", "Meta Platforms Ireland"),
    ("Bank of Ireland", "Bank of Ireland UK"),
    ("A-B", "AB"),
    ("AIB", "Allied Irish Banks"),
])
def test_conservative_non_merging(db, left, right):
    repository = CompanyRepository()
    assert repository.get_or_create_company(left).id != repository.get_or_create_company(right).id


def test_harmless_apostrophe_and_unicode_normalization():
    assert company_name("  O\u2019Brien   Group ")[1] == company_name("O'Brien Group")[1]
    assert company_name("Cafe\u0301")[1] == company_name("Caf\u00e9")[1]


def test_conflicting_known_domain_requires_review(db):
    repository = CompanyRepository()
    first = repository.get_or_create_company("Same Name", domain="one.test")
    with pytest.raises(ValueError):
        repository.get_or_create_company("same name", domain="two.test")
    assert repository.get(first.id).domain == "one.test"


def test_same_global_company_private_monitoring(users):
    a, b, _ = users
    company = CompanyRepository().get_or_create_company("Stripe")
    watch(a).monitor_company("a", company.id)
    assert watch(b).list_monitored_companies("b") == []
    watch(b).monitor_company("b", company.id)
    assert watch(a).list_monitored_companies("a")[0].company.id == company.id
    assert watch(b).list_monitored_companies("b")[0].company.id == company.id
    assert not hasattr(CompanyRepository().get(company.id), "candidate_id")


def test_monitor_idempotent_stop_and_reactivate(users):
    a = users[0]
    repository = watch(a)
    company = CompanyRepository().get_or_create_company("Zero Sources")
    assert CompanySourceRepository().list_company_sources(company.id) == []
    repository.monitor_company("a", company.id)
    first = repository.list_monitored_companies("a")[0]
    repository.monitor_company("a", company.id)
    assert len(repository.list_monitored_companies("a")) == 1
    repository.stop_monitoring_company("a", company.id)
    repository.stop_monitoring_company("a", company.id)
    assert repository.list_monitored_companies("a") == []
    repository.monitor_company("a", company.id)
    assert repository.list_monitored_companies("a")[0].created_at == first.created_at


@pytest.mark.parametrize("action", ["list", "add", "stop"])
def test_other_candidate_rejected(users, action):
    a = users[0]
    company = CompanyRepository().get_or_create_company("Private")
    with pytest.raises(PermissionError):
        if action == "list":
            watch(a).list_monitored_companies("b")
        elif action == "add":
            watch(a).monitor_company("b", company.id)
        else:
            watch(a).stop_monitoring_company("b", company.id)


def test_forged_active_context_and_role_rejected(users):
    a, b, _ = users
    forged = replace(a, access_level="admin")
    grant = AdminAccessSession({})
    grant.authorize(authenticated_user_id=a.id, target_user_id=b.id)
    with pytest.raises(PermissionError):
        watch(forged, b, grant).list_monitored_companies("b")


def test_admin_viewing_as_requires_matching_grant(users):
    a, b, admin = users
    with pytest.raises(PermissionError):
        watch(admin, b).list_monitored_companies("b")
    grant = AdminAccessSession({})
    grant.authorize(authenticated_user_id=admin.id, target_user_id=a.id)
    with pytest.raises(PermissionError):
        watch(admin, b, grant).list_monitored_companies("b")
    grant.authorize(authenticated_user_id=admin.id, target_user_id=b.id)
    company = CompanyRepository().get_or_create_company("Admin Selected")
    watch(admin, b, grant).monitor_company("b", company.id)
    assert len(watch(b).list_monitored_companies("b")) == 1
    assert watch(admin).list_monitored_companies("admin") == []
    grant.reset(authenticated_user_id=admin.id)
    with pytest.raises(PermissionError):
        watch(admin, b, grant).list_monitored_companies("b")


def test_deleted_or_reassociated_user_cannot_use_stale_context(users):
    a = users[0]
    with database.get_connection() as connection:
        connection.execute("UPDATE users SET candidate_id = NULL WHERE id = ?", (a.id,))
    with pytest.raises(PermissionError):
        watch(a).list_monitored_companies("a")


def test_company_sources_multiple_idempotent_and_disable(db):
    company = CompanyRepository().get_or_create_company("Employer")
    repository = CompanySourceRepository()
    first = repository.upsert_company_source(company.id, "Lever", "employer")
    same = repository.upsert_company_source(company.id, "lever", "employer", enabled=False)
    repository.upsert_company_source(company.id, "careers", "main", careers_url="https://employer.test/careers")
    repository.upsert_company_source(company.id, "future_feed", "main")
    rows = repository.list_company_sources(company.id)
    assert len(rows) == 3
    assert first.id == same.id
    assert first.created_at == same.created_at
    assert same.enabled is False
    assert repository.list_company_sources("missing") == []


def test_source_requires_company(db):
    with pytest.raises(ValueError):
        CompanySourceRepository().upsert_company_source("missing", "lever", "board")


@pytest.mark.parametrize("url", [
    "https://user:password@example.test/careers",
    "https://example.test/careers?api_key=secret",
    "https://example.test/#token=secret",
    "javascript:alert(1)",
])
def test_secret_bearing_or_invalid_urls_not_persisted(db, url):
    with pytest.raises(ValueError):
        CompanyRepository().get_or_create_company("Unsafe", careers_url=url)
    assert CompanyRepository().find_company("Unsafe") is None
    company = CompanyRepository().get_or_create_company("Safe")
    with pytest.raises(ValueError):
        CompanySourceRepository().upsert_company_source(company.id, "lever", "public", careers_url=url)
    assert CompanySourceRepository().list_company_sources(company.id) == []


def test_source_contract_has_no_secret_or_generic_metadata_fields(db):
    company = CompanyRepository().get_or_create_company("Public")
    with pytest.raises(TypeError):
        CompanySourceRepository().upsert_company_source(company.id, "lever", "board", api_key="secret")
    with pytest.raises(ValueError):
        CompanySourceRepository().upsert_company_source(company.id, "lever", "https://host?token=secret")
    assert CompanySourceRepository().list_company_sources(company.id) == []


def test_provider_bridge_lazy_unknown_and_disabled_sources(db):
    company = CompanyRepository().get_or_create_company("Employer")
    repository = CompanySourceRepository()
    supported = repository.upsert_company_source(company.id, "lever", "board")
    repository.upsert_company_source(company.id, "ashby", "off", enabled=False)
    repository.upsert_company_source(company.id, "future_feed", "unknown")
    calls = []
    def factory(row):
        calls.append(row)
        return SimpleNamespace(source_type=employer_run_name(row))
    sources = repository.list_company_sources(company.id)
    configs = build_employer_provider_configs(sources + sources, {"lever": factory})
    assert calls == []
    assert len(configs) == 1
    assert configs[0].source_type == employer_run_name(supported)
    assert configs[0].query_plan(day_index=0, source_type=configs[0].source_type) == [{"query": ""}]
    class Importer:
        def import_jobs(self, **kwargs):
            return dict(fetched=0, created=0, updated=0, unchanged=0)
    result = DailyIngestionService(Importer(), configs).run(0)
    assert calls == [supported]
    assert result.providers[employer_run_name(supported)].status == "success"


def test_multiple_employer_boards_have_distinct_run_names(db):
    repo = CompanySourceRepository()
    sources = [
        repo.upsert_company_source(CompanyRepository().get_or_create_company(name).id, "lever", name)
        for name in ("one", "two")
    ]
    configs = build_employer_provider_configs(sources, {"lever": lambda row: None})
    assert len({config.source_type for config in configs}) == 2


def test_initialization_rerun_preserves_watchlist_and_jobs(users):
    a = users[0]
    company = CompanyRepository().get_or_create_company("Keep")
    watch(a).monitor_company("a", company.id)
    with database.get_connection() as connection:
        before = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    database.initialize_database.cache_clear()
    database.initialize_database()
    assert watch(a).list_monitored_companies("a")[0].company.id == company.id
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == before
        assert connection.execute("SELECT COUNT(*) FROM candidate_career_objectives").fetchone()[0] == 0


def test_postgres_schema_rls_and_no_public_grants(monkeypatch):
    statements = []
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    database.create_company_registry_schema(SimpleNamespace(execute=statements.append))
    for table in ("companies", "candidate_monitored_companies", "company_job_sources"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
    assert not any("GRANT " in value or "CREATE POLICY" in value for value in statements)
    assert any("UNIQUE" in value and "normalized_name" in value for value in statements)
    assert any("PRIMARY KEY (candidate_id, company_id)" in value for value in statements)


def test_suggestion_lookup_does_not_start_monitoring(users):
    a = users[0]
    CompanyRepository().get_or_create_company("Suggested")
    assert CompanyRepository().find_company("Suggested") is not None
    assert watch(a).list_monitored_companies("a") == []
