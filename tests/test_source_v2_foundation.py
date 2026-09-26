from __future__ import annotations

from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest
import requests

from models.job import Job
from services import database
from services.daily_ingestion_service import DailyIngestionService
from services.global_source_schema import ensure_global_source_schema
from services.job_archive_service import JobArchiveService
from services.job_import_service import JobImportService
from services.job_observation import normalize_observation
from services.job_search_repository import JobSearchRepository
from services.job_source_repository import JobSourceRepository
from services.job_sources.provider import JobSourceProvider, ProviderConfig, default_providers


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("External calls are forbidden in Source V2 tests.")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(database, "DATABASE_FILE", tmp_path / "sources.db")
    database.initialize_database.cache_clear()
    database.initialize_database()
    yield
    database.initialize_database.cache_clear()


def job(identifier="alpha:1", url="https://jobs.example/vacancies/1"):
    return Job(
        id=identifier, title="Engineer", company="Acme", location="Dublin",
        url=url, raw_text="Engineer at Acme in Dublin", description="Build useful tools",
    )


class FakeProvider:
    def __init__(self, source_type="alpha", jobs=None):
        self.source_type = source_type
        self.jobs = jobs if jobs is not None else [job(source_type + ":1")]
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.jobs


def plan(**kwargs):
    return [{"query": "one"}, {"query": "two"}]


class FakeImport:
    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []

    def import_jobs(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["keywords"] == self.fail:
            raise RuntimeError("private-provider-payload-and-secret")
        return dict(fetched=3, created=1, updated=1, unchanged=1)


def test_arbitrary_registry_and_aggregation():
    importer = FakeImport()
    configs = tuple(ProviderConfig(name, lambda n=name: FakeProvider(n), query_plan=plan)
                    for name in ("alpha", "beta", "gamma"))
    result = DailyIngestionService(importer, configs).run(day_index=12)
    assert set(result.providers) == {"alpha", "beta", "gamma"}
    assert result.totals == dict(queries_run=6, fetched=18, created=6, updated=6, unchanged=6, failed_queries=0)
    assert all(value.status == "success" for value in result.providers.values())
    assert asdict(result)["providers"]["gamma"]["created"] == 2


def test_provider_factory_failure_isolated_and_sanitized(capsys):
    def broken():
        raise RuntimeError("secret-key-private-payload")
    configs = (
        ProviderConfig("broken", broken, query_plan=plan),
        ProviderConfig("ok", lambda: FakeProvider("ok"), query_plan=plan),
    )
    result = DailyIngestionService(FakeImport(), configs).run(0)
    assert result.providers["broken"].error_code == "provider_setup_failed"
    assert result.providers["broken"].queries_run == 0
    assert result.providers["ok"].queries_run == 2
    assert "secret-key" not in repr(asdict(result))
    assert capsys.readouterr().out == ""


def test_query_failure_isolated():
    result = DailyIngestionService(
        FakeImport("one"),
        (ProviderConfig("alpha", FakeProvider, query_plan=plan),),
    ).run(0).providers["alpha"]
    assert (result.queries_run, result.failed_queries, result.fetched) == (2, 1, 3)
    assert result.status == "partial"


def test_disabled_provider_is_never_constructed():
    def forbidden():
        pytest.fail("Disabled factory called")
    result = DailyIngestionService(FakeImport(), (ProviderConfig("off", forbidden, enabled=False),)).run(0)
    assert result.providers["off"].status == "disabled"
    assert result.totals["queries_run"] == 0


def test_duplicate_registry_names_rejected_before_fetch():
    config = ProviderConfig("alpha", FakeProvider)
    with pytest.raises(ValueError):
        DailyIngestionService(FakeImport(), (config, config)).run(0)


def test_empty_registry_does_not_use_defaults():
    assert DailyIngestionService(FakeImport(), ()).run(0).providers == {}


def test_default_registry_preserves_current_configuration(monkeypatch):
    from services.job_sources.adzuna_source import AdzunaJobSource
    from services.job_sources.jooble_source import JoobleJobSource
    monkeypatch.setenv("ADZUNA_APP_ID", "fake")
    monkeypatch.setenv("ADZUNA_APP_KEY", "fake")
    monkeypatch.setenv("JOOBLE_API_KEY", "fake")
    configs = default_providers(11, 12)
    assert [(c.source_type, c.location, c.results_per_query) for c in configs] == [
        ("jooble", "Ireland", 11), ("adzuna", "", 12),
    ]
    assert isinstance(configs[0].factory(), JoobleJobSource)
    assert isinstance(configs[1].factory(), AdzunaJobSource)
    assert configs[1].factory().country == "gb"
    assert all(isinstance(c.factory(), JobSourceProvider) for c in configs)
    result = DailyIngestionService(FakeImport()).run(1)
    assert result.jooble.queries_run == 20
    assert result.adzuna.queries_run == 10


@pytest.mark.parametrize("provider_name", ["adzuna", "jooble"])
def test_existing_provider_output_compatibility(monkeypatch, provider_name):
    from services.job_sources.adzuna_source import AdzunaJobSource
    from services.job_sources.jooble_source import JoobleJobSource
    monkeypatch.setenv("ADZUNA_APP_ID", "fake")
    monkeypatch.setenv("ADZUNA_APP_KEY", "fake")
    monkeypatch.setenv("JOOBLE_API_KEY", "fake")
    if provider_name == "adzuna":
        payload = {"results": [dict(id=7, title=" Engineer ", company={"display_name": "Acme"},
                                   location={"display_name": "Dublin"}, redirect_url="https://example/jobs/7",
                                   description="Build tools")]}
        method, provider = "get", AdzunaJobSource(country="gb")
    else:
        payload = {"jobs": [dict(id=7, title=" Engineer ", company="Acme", location="Dublin",
                                link="https://example/jobs/7", snippet="Build tools")]}
        method, provider = "post", JoobleJobSource()
    monkeypatch.setattr(requests, method, lambda *a, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: payload,
    ))
    observed = normalize_observation(provider.search("engineer", "Dublin")[0], provider_name)
    assert observed.job.id == provider_name + ":7"
    assert observed.job.title == "Engineer"
    assert observed.job.description == "Build tools"


def test_normalization_is_deterministic_and_non_mutating():
    original = replace(job("7"), title=" Engineer ", url=" HTTPS://Jobs.Example/a?id=7#role ", salary=70000)
    observed = normalize_observation(original, " Alpha ")
    assert observed.job.url == "https://jobs.example/a?id=7#role"
    assert observed.job.id == "alpha:7"
    assert observed.job.salary == "70000"
    assert original.title == " Engineer "
    assert normalize_observation(observed.job, "alpha").job == observed.job


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:password@example/jobs", "not-a-url"])
def test_invalid_observation_url_rejected(url):
    with pytest.raises(ValueError):
        normalize_observation(replace(job(), url=url), "alpha")


def import_job(value, source="alpha", user_id=None):
    return JobImportService().import_jobs(
        FakeProvider(source, [value]), source, "engineer", "Dublin", user_id=user_id,
    )


def test_repeated_observation_keeps_first_seen_and_refreshes_last_seen(db):
    assert import_job(job())["created"] == 1
    with database.get_connection() as connection:
        connection.execute("UPDATE job_sources SET discovered_at = ?, last_seen_at = ?",
                           ("2000-01-01", "2000-01-01"))
    assert import_job(job())["unchanged"] == 1
    with database.get_connection() as connection:
        rows = connection.execute("SELECT * FROM job_sources").fetchall()
        assert len(rows) == 1
        assert rows[0]["discovered_at"] == "2000-01-01"
        assert rows[0]["last_seen_at"] > "2000-01-01"
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
        assert connection.execute("SELECT description FROM jobs").fetchone()[0] == job().description


def test_multiple_providers_share_strong_equivalence(db):
    import_job(job())
    result = import_job(job("beta:7"), "beta")
    assert result["unchanged"] == 1
    rows = JobSourceRepository().list_sources_for_job("alpha:1")
    assert {row["source_type"] for row in rows} == {"alpha", "beta"}
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM candidate_job_analyses").fetchone()[0] == 0


def test_different_urls_never_merge_by_title_company_alone(db):
    import_job(job())
    assert import_job(job("beta:7", "https://jobs.example/vacancies/7"), "beta")["created"] == 1


def test_provider_identifiers_are_namespaced(db):
    import_job(job("7", ""), "alpha")
    assert import_job(job("7", ""), "beta")["created"] == 1


def test_launch_overlap_tracking_query_deduplicates(db):
    import_job(job())
    other = job("beta:7", job().url + "?utm_source=other")
    assert import_job(other, "beta")["unchanged"] == 1


def test_launch_overlap_changed_provider_id_reuses_exact_job(db):
    import_job(job())
    assert import_job(job("alpha:replacement"))["unchanged"] == 1
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_launch_overlap_ambiguous_canonical_matches_do_not_merge(db):
    import_job(job())
    import_job(job("beta:7", "https://jobs.example/vacancies/7"), "beta")
    # Reproduce legacy duplicate rows with two equally strong matches.
    with database.get_connection() as connection:
        connection.execute("UPDATE jobs SET url = ?", (job().url,))
    assert import_job(job("gamma:9"), "gamma")["created"] == 1
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3


@pytest.mark.parametrize("field,value", [("title", "Senior Engineer"), ("company", "Other"), ("location", "London")])
def test_launch_overlap_same_url_conflicting_metadata_stays_separate(db, field, value):
    import_job(job())
    assert import_job(replace(job("beta:7"), **{field: value}), "beta")["created"] == 1


def test_private_source_scope_and_global_search(db):
    from services.user_repository import UserRepository
    users = [UserRepository().create(email=f"{i}@example.test", display_name="User") for i in range(2)]
    import_job(job("manual:1"), "manual", users[0].id)
    assert JobSearchRepository().list_global_jobs() == []
    assert len(JobSearchRepository().list_user_jobs(users[0].id)) == 1
    assert JobSearchRepository().list_user_jobs(users[1].id) == []
    private_id = JobSourceRepository().list_by_user(users[0].id)[0]
    assert private_id.startswith("private:")
    assert JobSourceRepository().list_sources_for_job(private_id) == []
    assert len(JobSourceRepository().list_sources_for_job(private_id, users[0].id)) == 1
    assert JobSourceRepository().list_sources_for_job(private_id, users[1].id) == []
    assert import_job(job())["created"] == 1
    assert len(JobSearchRepository().list_global_jobs()) == 1


@pytest.mark.parametrize("source", ["gmail", "gmail_linkedin", "manual", "import"])
def test_personal_source_cannot_be_global(source):
    provider = FakeProvider(source)
    with pytest.raises(ValueError):
        JobImportService().import_jobs(provider, source, "", "")
    assert provider.calls == []


def test_archive_and_reappearance(db):
    import_job(job())
    with database.get_connection() as connection:
        connection.execute("UPDATE job_sources SET last_seen_at = ?", ("2000-01-01",))
    archive = JobArchiveService()
    # Age alone no longer provides closure evidence (Launch 1D).
    assert archive.archive_stale_global_jobs() == 0
    with database.get_connection() as connection:
        connection.execute("UPDATE jobs SET archived_at = ?", ("2000-01-02",))
    assert JobSearchRepository().list_global_jobs() == []
    import_job(job())
    assert len(JobSearchRepository().list_global_jobs()) == 1
    assert archive.archive_stale_global_jobs() == 0


def test_personal_source_prevents_global_archiving(db):
    from services.user_repository import UserRepository
    user = UserRepository().create("private@example.test", "User")
    import_job(job())
    JobSourceRepository().add_source("alpha:1", "manual", user.id)
    with database.get_connection() as connection:
        connection.execute("UPDATE job_sources SET last_seen_at = ?", ("2000-01-01",))
    assert JobArchiveService().archive_stale_global_jobs() == 0


def test_legacy_sqlite_provenance_upgrade_preserves_rows():
    import sqlite3
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE users (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY)")
        connection.execute("""CREATE TABLE job_sources (
            job_id TEXT NOT NULL, user_id TEXT NOT NULL, source_type TEXT NOT NULL,
            discovered_at TEXT NOT NULL, PRIMARY KEY(job_id, user_id, source_type)
        )""")
        connection.execute("INSERT INTO users VALUES ('u')")
        connection.execute("INSERT INTO jobs VALUES ('j')")
        connection.execute("INSERT INTO job_sources VALUES ('j', 'u', 'manual', '2020-01-01')")
        ensure_global_source_schema(connection, postgres=False)
        ensure_global_source_schema(connection, postgres=False)
        row = connection.execute("SELECT * FROM job_sources").fetchone()
        assert (row["user_id"], row["source_type"], row["last_seen_at"]) == ("u", "manual", "2020-01-01")
        connection.execute("""INSERT INTO job_sources (
            job_id, source_type, discovered_at, last_seen_at
        ) VALUES ('j', 'alpha', '2026-01-01', '2026-01-01')""")
        assert connection.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0] == 2


def test_postgres_schema_double_preserves_existing_primary_key():
    statements = []
    class Connection:
        def execute(self, statement):
            statements.append(str(statement))
            return SimpleNamespace(
                fetchone=lambda: {"conname": "job_sources_pkey"},
                fetchall=lambda: [{"column_name": "source_id"}],
            )
    ensure_global_source_schema(Connection(), postgres=True)
    assert "SELECT pg_advisory_xact_lock(731302)" == statements[0]
    assert not any("DROP CONSTRAINT" in s for s in statements)
    assert any("WHERE user_id IS NULL" in s for s in statements)
    assert any("WHERE user_id IS NOT NULL" in s for s in statements)


def test_archive_postgres_adapter_translates_placeholders(monkeypatch):
    from contextlib import contextmanager
    import services.job_archive_service as archive_module
    recorded = []
    class Driver:
        def execute(self, query, params):
            recorded.append((query, params))
            return SimpleNamespace(rowcount=0)
    @contextmanager
    def connection():
        yield database.PostgresConnectionAdapter(Driver())
    monkeypatch.setattr(archive_module, "get_connection", connection)
    JobArchiveService().archive_stale_global_jobs()
    assert "%s" in recorded[0][0]
    assert "BOOL_AND" not in recorded[0][0]


def test_candidate_discovery_only_includes_global_and_own_personal_jobs(db):
    from models.candidate import Candidate
    from services.candidate_repository import CandidateRepository
    from services.user_repository import UserRepository
    for identifier in ("a", "b"):
        CandidateRepository().save(Candidate(
            id=identifier, name=identifier, current_role="", current_level="",
            professional_summary="",
        ))
        UserRepository().create(identifier + "@example.test", identifier,
                                candidate_id=identifier, user_id=identifier)
    import_job(job("manual:private"), "manual", "a")
    private_id = JobSourceRepository().list_by_user("a")[0]
    import_job(job("alpha:public"))
    repo = JobSearchRepository()
    own = repo.list_jobs_to_analyze_for_candidate("a", "v1", "signature")
    other = repo.list_jobs_to_analyze_for_candidate("b", "v1", "signature")
    assert {row["id"] for row in own} == {private_id, "alpha:public"}
    assert {row["id"] for row in other} == {"alpha:public"}
    assert repo.count_jobs_to_analyze_for_candidate("a", "v1", "signature") == len(own)
    assert repo.count_jobs_to_analyze_for_candidate("b", "v1", "signature") == len(other)


@pytest.fixture
def discovery_pool(db):
    from models.candidate import Candidate
    from services.candidate_repository import CandidateRepository
    from services.user_repository import UserRepository
    for identifier in ("a", "b"):
        CandidateRepository().save(Candidate(
            id=identifier, name=identifier, current_role="", current_level="",
            professional_summary="",
        ))
        UserRepository().create(identifier + "@example.test", identifier,
                                candidate_id=identifier, user_id="user-" + identifier)

    def add(identifier, title, owner=None, source=True):
        with database.get_connection() as connection:
            connection.execute(
                "INSERT INTO jobs (id, title, company, location, created_at, updated_at) "
                "VALUES (?, ?, 'Acme', 'Dublin', ?, ?)",
                (identifier, title, "2026-01-01", "2026-01-01"),
            )
        if source:
            JobSourceRepository().add_source(
                job_id=identifier, source_type="manual" if owner else "alpha", user_id=owner,
            )
    return add


def test_discovery_count_and_list_share_visibility_and_lifecycle(discovery_pool):
    for identifier, owner, source in (
        ("global", None, True), ("own", "user-a", True),
        ("foreign", "user-b", True), ("no-source", None, False),
        ("archived", None, True), ("analyzed", None, True), ("pending", None, True),
    ):
        discovery_pool(identifier, identifier, owner, source)
    JobSourceRepository().add_source(job_id="global", source_type="beta", user_id=None)
    database.ensure_candidate_job_analysis("a", "analyzed")
    database.ensure_candidate_job_analysis("a", "pending")
    with database.get_connection() as connection:
        connection.execute("UPDATE jobs SET archived_at = '2026-01-02' WHERE id = 'archived'")
        connection.execute("UPDATE candidate_job_analyses SET analysis_state = 'analyzed' "
                           "WHERE candidate_id = 'a' AND job_id = 'analyzed'")
    repo = JobSearchRepository()
    for candidate, expected in (
        ("a", {"global", "own", "pending"}),
        ("b", {"global", "foreign", "pending", "analyzed"}),
    ):
        rows = repo.list_jobs_to_analyze_for_candidate(candidate, "v1", "signature")
        assert {row["id"] for row in rows} == expected
        assert repo.count_jobs_to_analyze_for_candidate(candidate, "v1", "signature") == len(expected)


@pytest.mark.parametrize("state,archived", [("analyzed", False), ("pending", False),
                                             ("analyzed", True)])
def test_discovery_skips_unlinkable_equivalent_and_reaches_next_job(discovery_pool, state, archived):
    discovery_pool("original", "Engineer")
    discovery_pool("duplicate", " ENGINEER ")
    discovery_pool("next", "Different role")
    assert database.ensure_candidate_job_analysis("a", "original")
    with database.get_connection() as connection:
        connection.execute("UPDATE candidate_job_analyses SET analysis_state = ? WHERE candidate_id = 'a'",
                           (state,))
        connection.execute("UPDATE jobs SET created_at = '2099-01-01' WHERE id = 'duplicate'")
        if archived:
            connection.execute("UPDATE jobs SET archived_at = '2026-01-02' WHERE id = 'original'")
    # This is the production failure: selecting this ID cannot create a pending link.
    assert not database.ensure_candidate_job_analysis("a", "duplicate")
    repo = JobSearchRepository()
    rows = repo.list_jobs_to_analyze_for_candidate("a", "v1", "signature")
    expected = {"next", "original"} if state == "pending" else {"next"}
    assert {row["id"] for row in rows} == expected
    assert repo.count_jobs_to_analyze_for_candidate("a", "v1", "signature") == len(expected)
    selected = repo.list_jobs_to_analyze_for_candidate("a", "v1", "signature", limit=1)[0]
    database.ensure_candidate_job_analysis("a", selected["id"])
    assert [row["id"] for row in database.list_pending_candidate_jobs(
        "a", limit=1, job_ids=[selected["id"]],
    )] == [selected["id"]]
    # Another candidate's equivalent link must not suppress this candidate's pool.
    other = repo.list_jobs_to_analyze_for_candidate("b", "v1", "signature")
    assert {row["id"] for row in other} == ({"duplicate", "next"} if archived else
                                           {"original", "duplicate", "next"})
    assert repo.count_jobs_to_analyze_for_candidate("b", "v1", "signature") == len(other)


def test_discovery_respects_active_claims_and_recovers_expired_claims(discovery_pool, monkeypatch):
    import services.job_search_repository as search_module
    now = "2026-09-20T12:00:00+00:00"
    monkeypatch.setattr(search_module, "utc_now", lambda: now, raising=False)
    for identifier in ("claimed", "available"):
        discovery_pool(identifier, identifier)
    database.ensure_candidate_job_analysis("a", "claimed")
    with database.get_connection() as connection:
        connection.execute("UPDATE jobs SET created_at = '2099-01-01' WHERE id = 'claimed'")
        connection.execute(
            "UPDATE candidate_job_analyses SET analysis_claim_token = 'other-worker', "
            "analysis_claim_expires_at = ? WHERE candidate_id = 'a' AND job_id = 'claimed'",
            ("2026-09-20T12:30:00+00:00",),
        )
    repo = JobSearchRepository()
    assert [r["id"] for r in repo.list_jobs_to_analyze_for_candidate("a", "v1", "sig")] == ["available"]
    assert repo.count_jobs_to_analyze_for_candidate("a", "v1", "sig") == 1
    assert len(repo.list_jobs_to_analyze_for_candidate("b", "v1", "sig")) == 2
    assert repo.count_jobs_to_analyze_for_candidate("b", "v1", "sig") == 2
    monkeypatch.setattr(search_module, "utc_now", lambda: "2026-09-20T12:30:00+00:00")
    assert len(repo.list_jobs_to_analyze_for_candidate("a", "v1", "sig")) == 2
    assert repo.count_jobs_to_analyze_for_candidate("a", "v1", "sig") == 2


def test_discovery_run_exclusions_are_bound_and_do_not_change_later_search(discovery_pool):
    for identifier in ("one", "two", "quote'job"):
        discovery_pool(identifier, identifier)
    repo = JobSearchRepository()
    assert [r["id"] for r in repo.list_jobs_to_analyze_for_candidate(
        "a", "v1", "sig", exclude_job_ids=["one", "quote'job"],
    )] == ["two"]
    assert repo.list_jobs_to_analyze_for_candidate(
        "a", "v1", "sig", exclude_job_ids=["one", "two", "quote'job"],
    ) == []
    assert len(repo.list_jobs_to_analyze_for_candidate("a", "v1", "sig")) == 3
    assert repo.count_jobs_to_analyze_for_candidate("a", "v1", "sig") == 3


def test_gmail_processor_keeps_personal_provenance(db, monkeypatch):
    from services.gmail_job_processor import GmailJobProcessor
    from services.user_repository import UserRepository
    user = UserRepository().create("gmail@example.test", "User")
    calls = []
    messages = SimpleNamespace(
        list_pending=lambda **kw: [{"gmail_message_id": "private-message", "raw_html": "fixture"}],
        mark_processed=lambda **kw: calls.append(kw),
        mark_failed=lambda **kw: pytest.fail("Gmail fixture processing failed"),
    )
    monkeypatch.setattr("services.gmail_job_processor.extract_jobs_from_email",
                        lambda **kw: SimpleNamespace(jobs={"one": job("email-job")}, source="linkedin"))
    result = GmailJobProcessor(gmail_message_repository=messages).process_pending_messages(user.id)
    assert result.jobs_created == 1
    assert len(calls) == 1
    assert JobSearchRepository().list_global_jobs() == []
    private_id = JobSourceRepository().list_by_user(user.id)[0]
    row = JobSourceRepository().list_sources_for_job(private_id, user.id)[0]
    assert row["source_type"] == "gmail_linkedin"
    assert "private-message" not in repr(dict(row))


def test_recent_observation_from_any_provider_prevents_archive(db):
    import_job(job())
    import_job(job("beta:7"), "beta")
    with database.get_connection() as connection:
        connection.execute("UPDATE job_sources SET last_seen_at = ? WHERE source_type = ?",
                           ("2000-01-01", "alpha"))
    assert JobArchiveService().archive_stale_global_jobs() == 0


def test_postgres_legacy_primary_key_upgrade_double():
    statements = []
    class Connection:
        def execute(self, statement):
            statements.append(str(statement))
            return SimpleNamespace(
                fetchone=lambda: {"conname": "legacy_key"},
                fetchall=lambda: [{"column_name": "job_id"}, {"column_name": "user_id"}],
            )
    ensure_global_source_schema(Connection(), postgres=True)
    assert any("DROP CONSTRAINT" in s for s in statements)
    assert any("ADD PRIMARY KEY (source_id)" in s for s in statements)


def test_reappearance_maintenance_clears_archive_after_new_observation(db):
    import_job(job())
    with database.get_connection() as connection:
        connection.execute("UPDATE jobs SET archived_at = ?", ("2000-01-01",))
    assert JobArchiveService().reactivate_seen_global_jobs() == 1
    assert len(JobSearchRepository().list_global_jobs()) == 1
