from dataclasses import replace
from types import SimpleNamespace

import pytest

from models.job import Job
from services import database
from services.gmail_job_processor import GmailJobProcessor
from services.job_import_service import JobImportService
from services.user_repository import UserRepository


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("External calls are forbidden.")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.fixture
def owners():
    return [UserRepository().create(f"owner-{n}@example.test", "Synthetic") for n in range(2)]


def vacancy(identifier="1", **changes):
    return replace(Job(identifier, "Public vacancy", "https://jobs.example/1",
                       title="Engineer", company="Example", location="Dublin",
                       description="Public description"), **changes)


def ingest(job, source="alpha", owner=None):
    return JobImportService().import_jobs(
        SimpleNamespace(search=lambda **kw: [job]), source, "", "", user_id=owner,
    )


def rows(table="jobs"):
    assert table in {"jobs", "job_observations", "job_sources"}
    with database.get_connection() as conn:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]


@pytest.mark.parametrize("reverse", [False, True])
def test_private_imports_never_overwrite_another_owner(owners, reverse):
    a, b = owners[::-1] if reverse else owners
    ingest(vacancy(), "manual", a.id)
    original = rows()[0]
    ingest(vacancy(raw_text="Private replacement " * 20, title="Private title",
                   company="Private company", description="Private description"), "manual", b.id)
    assert next(r for r in rows() if r["id"] == original["id"]) == original
    assert len(rows()) == 2
    assert {r["user_id"] for r in rows("job_observations")} == {a.id, b.id}


@pytest.mark.parametrize("reverse", [False, True])
def test_gmail_collision_cannot_replace_shared_job(owners, reverse):
    a, b = owners[::-1] if reverse else owners
    def process(owner, title):
        messages = SimpleNamespace(
            list_pending=lambda **kw: [dict(gmail_message_id="fake", sender="alerts@linkedin.com",
                raw_html=f'<a href="https://www.linkedin.com/jobs/view/123/">{title}</a>')],
            mark_processed=lambda **kw: None,
            mark_failed=lambda **kw: pytest.fail("Gmail processing failed"),
        )
        return GmailJobProcessor(messages).process_pending_messages(owner.id)
    process(a, "Original")
    original = rows()[0]
    process(b, "Private replacement " * 20)
    assert next(r for r in rows() if r["id"] == original["id"]) == original
    assert len(rows()) == 2
    assert process(b, "Private replacement " * 20).jobs_unchanged == 1
    assert len(rows("job_observations")) == 2


def test_private_observations_can_reference_public_canonical_without_overwriting(owners):
    ingest(vacancy())
    original = rows()[0]
    for owner in owners:
        ingest(vacancy(raw_text="Private note " * 20, description="Private detail"), "manual", owner.id)
    assert rows() == [original]
    assert {r["user_id"] for r in rows("job_sources") if r["user_id"]} == {u.id for u in owners}


def test_provider_namespaces_do_not_collide():
    ingest(vacancy(url="https://jobs.example/a"), "alpha")
    ingest(vacancy(url="https://jobs.example/b"), "beta")
    assert {r["id"] for r in rows()} == {"alpha:1", "beta:1"}


@pytest.mark.parametrize("order", [("alpha", "beta"), ("beta", "alpha")])
def test_public_sources_use_explicit_provenance_not_length(order):
    for source in order:
        ingest(vacancy(raw_text="Longer lower priority " * 20 if source == "beta" else "Short",
                       description=source), source)
    assert len(rows()) == 1
    assert rows()[0]["description"] == "alpha"
    assert len(rows("job_observations")) == 2


def test_tracking_parameters_deduplicate_but_identity_parameters_do_not():
    ingest(vacancy())
    ingest(vacancy(url="https://jobs.example/1?utm_source=email&utm_campaign=test"), "beta")
    assert len(rows()) == 1
    ingest(vacancy(url="https://jobs.example/1?id=another"), "gamma")
    assert len(rows()) == 2


@pytest.mark.parametrize("field", ["title", "company"])
def test_conflicting_identity_does_not_attach_private_source(owners, field):
    ingest(vacancy())
    ingest(vacancy(**{field: "Different"}), "manual", owners[0].id)
    assert len(rows()) == 2
    assert next(r for r in rows() if r["id"] == "alpha:1")[field] == getattr(vacancy(), field)


def test_unscoped_raw_writer_is_insert_only():
    database.upsert_raw_job(vacancy())
    assert database.upsert_raw_job(vacancy(raw_text="Changed " * 20)) == "unchanged"
    assert rows()[0]["raw_text"] == "Public vacancy"


def test_source_deletion_preserves_other_owner_and_canonical(owners):
    ingest(vacancy())
    for owner in owners:
        ingest(vacancy(), "manual", owner.id)
    with database.get_connection() as conn:
        conn.execute("DELETE FROM job_sources WHERE user_id = ?", (owners[0].id,))
    assert len(rows()) == 1
    assert any(r["user_id"] == owners[1].id for r in rows("job_sources"))


def test_private_retry_is_idempotent_and_observation_reads_are_scoped(owners):
    ingest(vacancy(), "manual", owners[0].id)
    assert ingest(vacancy(), "manual", owners[0].id)["unchanged"] == 1
    from services.job_observation_repository import JobObservationRepository
    repo = JobObservationRepository()
    assert len(repo.list_for_user(owners[0].id)) == 1
    assert repo.list_for_user(owners[1].id) == []
    assert len(rows()) == len(rows("job_observations")) == 1


def test_private_caller_cannot_claim_public_provider_authority(owners):
    ingest(vacancy())
    original = rows()[0]
    ingest(vacancy(raw_text="Private " * 30, description="Private"), "alpha", owners[0].id)
    assert rows() == [original]


@pytest.mark.parametrize("private_first", [True, False])
def test_public_content_never_inherits_private_observations(owners, private_first):
    private = vacancy(raw_text="Private " * 20, description="Private")
    if private_first:
        ingest(private, "manual", owners[0].id)
    ingest(vacancy())
    if not private_first:
        ingest(private, "manual", owners[0].id)
    public = next(r for r in rows() if r["id"] == "alpha:1")
    assert public["description"] == "Public description"
    assert public["raw_text"] == "Public vacancy"


def test_changed_url_with_same_private_id_is_not_same_identity(owners):
    ingest(vacancy(), "manual", owners[0].id)
    ingest(vacancy(url="https://jobs.example/another"), "manual", owners[0].id)
    assert len(rows()) == 2


def test_atomic_observation_failure_rolls_back_and_retry_succeeds(owners):
    from services.job_observation_repository import JobObservationRepository
    class BrokenSources:
        def add_source(self, *args, **kwargs):
            raise RuntimeError("synthetic failure")
    with pytest.raises(RuntimeError):
        JobObservationRepository(BrokenSources()).record(vacancy(), "manual", user_id=owners[0].id)
    assert rows() == rows("job_sources") == rows("job_observations") == []
    assert ingest(vacancy(), "manual", owners[0].id)["created"] == 1


def test_retry_after_committed_observation_does_not_duplicate(owners):
    # Models the crash window after the transaction but before marking an email processed.
    from services.job_observation_repository import JobObservationRepository
    repo = JobObservationRepository()
    first = repo.record(vacancy(), "gmail_linkedin", user_id=owners[0].id)
    second = repo.record(vacancy(), "gmail_linkedin", user_id=owners[0].id)
    assert first[0] == second[0] and second[1] == "unchanged"
    assert len(rows()) == len(rows("job_sources")) == len(rows("job_observations")) == 1


def test_two_concurrent_public_imports_deduplicate():
    from concurrent.futures import ThreadPoolExecutor
    import threading
    barrier = threading.Barrier(2)
    def run(source):
        barrier.wait(timeout=5)
        return ingest(vacancy(description=source), source)
    with ThreadPoolExecutor(2) as workers:
        list(workers.map(run, ["alpha", "beta"]))
    assert len(rows()) == 1
    assert rows()[0]["description"] == "alpha"
    assert len(rows("job_observations")) == 2


def test_migration_is_additive_idempotent_and_does_not_infer_legacy_authority():
    from services.job_observation_schema import migrate_job_observations
    database.upsert_raw_job(vacancy("alpha:1"))
    from services.job_source_repository import JobSourceRepository
    JobSourceRepository().add_source("alpha:1", "alpha")
    original = rows()[0]
    with database.get_connection() as conn:
        migrate_job_observations(conn)
        migrate_job_observations(conn)
        assert conn.execute("SELECT COUNT(*) FROM job_content_authority").fetchone()[0] == 0
    ingest(vacancy(description="Different", raw_text="Longer " * 30))
    assert rows() == [original]


def test_candidate_lifecycle_and_shared_profile_remain_unchanged(owners):
    from models.candidate import Candidate
    from services.candidate_repository import CandidateRepository
    from services.job_profile_manager import JobProfileManager
    ingest(vacancy())
    CandidateRepository().save(Candidate("candidate", "Synthetic", "", "", ""))
    database.ensure_candidate_job_analysis("candidate", "alpha:1")
    JobProfileManager(None).ensure_table()
    with database.get_connection() as conn:
        conn.execute("UPDATE candidate_job_analyses SET status = 'applied' WHERE candidate_id = 'candidate'")
        conn.execute("INSERT INTO job_profiles VALUES (?, ?, ?, ?, ?, ?)",
                     ("alpha:1", "{}", "signature", "version", "before", "before"))
        before = dict(conn.execute("SELECT * FROM candidate_job_analyses").fetchone())
    ingest(vacancy(description="Private", raw_text="Private " * 30), "manual", owners[0].id)
    with database.get_connection() as conn:
        assert dict(conn.execute("SELECT * FROM candidate_job_analyses").fetchone()) == before
        assert conn.execute("SELECT job_signature FROM job_profiles").fetchone()[0] == "signature"


def test_enrichment_cannot_replace_canonical_or_legacy_content():
    ingest(vacancy())
    original = rows()[0]
    database.update_shared_job_analysis_data(vacancy("alpha:1", description="Replacement"))
    assert rows() == [original]
    database.upsert_raw_job(vacancy("legacy", description=None))
    database.update_shared_job_analysis_data(vacancy("legacy", description="Unattributed"))
    assert next(r for r in rows() if r["id"] == "legacy")["description"] is None


def test_postgres_migration_has_rls_and_no_legacy_data_rewrite():
    from services.job_observation_schema import migrate_job_observations
    sql = []
    migrate_job_observations(SimpleNamespace(execute=lambda query: sql.append(query)), postgres=True)
    assert sum("ENABLE ROW LEVEL SECURITY" in query for query in sql) == 2
    assert sum("FROM anon" in query for query in sql) == 2
    assert sum("FROM authenticated" in query for query in sql) == 2
    assert not any(query.lstrip().startswith(("UPDATE", "DELETE", "INSERT")) for query in sql)


def test_postgres_transaction_locks_before_reading_identity(monkeypatch):
    from contextlib import contextmanager
    from services import job_observation_repository as module
    calls = []
    real_connection = database.get_connection
    class Driver:
        def __init__(self, conn):
            self.conn = conn
        def execute(self, query, params=None):
            calls.append(query)
            if "pg_advisory_xact_lock" in query:
                self.conn.execute("BEGIN IMMEDIATE")
                return None
            assert "?" not in query
            return self.conn.execute(query.replace("%s", "?"), params or ())
    @contextmanager
    def adapter():
        with real_connection() as conn:
            yield database.PostgresConnectionAdapter(Driver(conn))
    monkeypatch.setattr(module, "get_connection", adapter)
    monkeypatch.setattr(module, "is_postgres", lambda: True)
    ingest(vacancy())
    assert calls[0] == "SELECT pg_advisory_xact_lock(731304)"
    assert len(rows()) == 1


def test_public_authority_is_explicit_and_cannot_be_claimed_by_gmail():
    from services.job_observation_repository import JobObservationRepository
    repo = JobObservationRepository()
    with pytest.raises(ValueError, match="explicit source authority"):
        repo.record(vacancy(), "alpha")
    with pytest.raises(ValueError, match="owner"):
        repo.record(vacancy(), "gmail_linkedin", trusted_public=True)
    assert rows() == []


def test_unprovenanced_id_collision_never_promotes_legacy_content():
    database.upsert_raw_job(vacancy("alpha:1", description="Unclassified private legacy content"))
    ingest(vacancy())
    source = rows("job_sources")[0]
    assert source["job_id"] != "alpha:1"
    assert next(r for r in rows() if r["id"] == source["job_id"])["description"] == "Public description"


@pytest.mark.parametrize("reverse", [False, True])
def test_each_private_owner_keeps_own_content_regardless_of_order(owners, reverse):
    observations = [(owners[0], vacancy(description="A", raw_text="Short")),
                    (owners[1], vacancy(description="B", raw_text="Longer " * 30))]
    for owner, value in reversed(observations) if reverse else observations:
        ingest(value, "manual", owner.id)
    for owner, value in observations:
        source = next(r for r in rows("job_sources") if r["user_id"] == owner.id)
        actual = next(r for r in rows() if r["id"] == source["job_id"])
        assert actual["description"] == value.description
        assert actual["raw_text"] == value.raw_text.strip()


def test_public_refresh_from_selected_authority_can_be_shorter():
    ingest(vacancy(raw_text="Long initial description " * 10))
    assert ingest(vacancy(raw_text="Short correction", description="Corrected"))["updated"] == 1
    assert rows()[0]["raw_text"] == "Short correction"


def test_enrichment_requires_canonical_url_and_does_not_repeat_overwrite():
    ingest(vacancy(description=None))
    database.update_shared_job_analysis_data(vacancy("alpha:1", url="https://other.example/job", description="Wrong URL"))
    assert rows()[0]["description"] is None
    database.update_shared_job_analysis_data(vacancy("alpha:1", description="Fetched public"))
    assert rows()[0]["description"] == "Fetched public"
    ingest(vacancy(description=None))
    assert rows()[0]["description"] == "Fetched public"


def test_user_deletion_does_not_delete_shared_public_job(owners):
    ingest(vacancy())
    for owner in owners:
        ingest(vacancy(), "manual", owner.id)
    with database.get_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (owners[0].id,))
    assert len(rows()) == 1
    assert any(r["user_id"] == owners[1].id for r in rows("job_sources"))


def test_manual_page_routes_through_owned_observations():
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).parents[1] / "pages" / "2_Sources.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert not any(isinstance(n.func, ast.Name) and n.func.id == "upsert_raw_job" for n in calls)
    writes = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "record"
              and isinstance(n.func.value, ast.Call) and isinstance(n.func.value.func, ast.Name)
              and n.func.value.func.id == "JobObservationRepository"]
    assert len(writes) == 1
    assert any(k.arg == "user_id" and isinstance(k.value, ast.Attribute) and k.value.attr == "id"
               for k in writes[0].keywords)


def test_provider_boundary_only_fields_are_not_persisted():
    from dataclasses import dataclass
    from datetime import datetime, timezone
    from services.job_sources.employer_board import BoardJob
    @dataclass
    class ExtendedJob(BoardJob):
        private_metadata: str = "must-not-persist"
    job = ExtendedJob("one", "Public", "https://jobs.example/1", title="Engineer",
                      published_at=datetime.now(timezone.utc))
    assert ingest(job)["created"] == 1
    assert "published_at" not in rows("job_observations")[0]["payload_json"]
    assert "must-not-persist" not in repr(rows("job_observations"))


def test_legacy_shared_private_job_is_not_rewritten_or_promoted(owners):
    from services.job_source_repository import JobSourceRepository
    legacy = vacancy("manual:1", description="Legacy owner content")
    database.upsert_raw_job(legacy)
    sources = JobSourceRepository()
    for owner in owners:
        sources.add_source(legacy.id, "manual", owner.id)
    before = rows()[0]
    ingest(vacancy(raw_text="Overwrite attempt " * 30), "manual", owners[1].id)
    assert next(r for r in rows() if r["id"] == legacy.id) == before
    assert len(sources.list_sources_for_job(legacy.id, owners[0].id)) == 1
    assert len(sources.list_sources_for_job(legacy.id, owners[1].id)) == 1
    assert all(r["user_id"] is not None for r in rows("job_sources"))
