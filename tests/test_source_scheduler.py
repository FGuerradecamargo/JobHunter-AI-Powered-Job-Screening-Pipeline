from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

from services import database
from services.company_repository import CompanyRepository
from services.company_source_repository import CompanySourceRepository
from services.daily_ingestion_service import SourceIngestionResult
from services.employer_provider_factories import employer_provider_factories
from services.job_archive_service import JobArchiveService
from services.job_sources.board_http import BoardError
from services.job_sources.provider import ProviderConfig
from services.source_run_repository import SourceRunRepository
from services.source_run_schema import create_source_run_schema
from services.source_schedule_service import SourceScheduleService, SchedulePolicy


NOW = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("Scheduler tests forbid external calls.")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(requests.sessions.Session, "request", denied)


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(database, "DATABASE_FILE", tmp_path / "scheduler.db")
    database.initialize_database.cache_clear()
    database.initialize_database()
    yield
    database.initialize_database.cache_clear()


def board(vendor="lever", key="acme"):
    company = CompanyRepository().get_or_create_company("Acme")
    return CompanySourceRepository().upsert_company_source(company.id, vendor, key)


class Clock:
    def __init__(self):
        self.now = NOW
    def __call__(self):
        return self.now


class Provider:
    def __init__(self, identity, error=None, skipped=0):
        self.source_type = identity
        self.error = error
        self.skipped_records = skipped
        self.calls = 0
    def search(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return []


def scheduler(row, provider, clock=None):
    return SourceScheduleService(clock=clock or Clock(), factories={row.source_type: lambda _: provider})


@pytest.mark.parametrize("vendor", ["lever", "ashby"])
def test_due_success_and_cadence(db, vendor):
    row = board(vendor)
    identity = f"{vendor}:{row.id}"
    p, clock = Provider(identity), Clock()
    service = scheduler(row, p, clock)
    assert service.run([], [row])[0]["coverage_complete"] is True
    assert service.run([], [row])[0]["status"] == "skipped_not_due"
    assert p.calls == 1
    clock.now += timedelta(hours=6)
    assert service.run([], [row])[0]["status"] == "success"
    assert p.calls == 2
    runs = SourceRunRepository().list_runs(identity)
    assert len(runs) == 2 and runs[0]["next_eligible_at"] == (clock.now + timedelta(hours=6)).isoformat()


def test_global_rotation_runs_at_most_daily_and_not_board_coverage(db):
    p, clock = Provider("jooble"), Clock()
    config = ProviderConfig("jooble", lambda: p, query_plan=lambda **_: [{"query": "rotation"}])
    service = SourceScheduleService(clock=clock)
    result = service.run([config], [])[0]
    assert result["status"] == "success" and not result["coverage_complete"]
    clock.now += timedelta(hours=23)
    assert service.run([config], [])[0]["status"] == "skipped_not_due"
    clock.now += timedelta(hours=1)
    assert service.run([config], [])[0]["status"] == "success"


def test_disabled_and_duplicate_sources(db):
    row = board()
    p = Provider(f"lever:{row.id}")
    service = scheduler(row, p)
    assert service.run([], [replace(row, enabled=False)])[0]["status"] == "disabled"
    assert p.calls == 0
    service.run([], [row, row, row])
    assert p.calls == 1


@pytest.mark.parametrize("error,code,minutes", [
    (BoardError("rate_limited"), "rate_limited", 120),
    (BoardError("transport_retry_exhausted"), "transport_failure", 30),
    (BoardError("response_shape"), "response_shape", 360),
    (BoardError("pagination_limit"), "response_shape", 360),
    (RuntimeError("secret-payload"), "query_failed", 30),
])
def test_failure_backoff_sanitized_and_no_busy_loop(db, error, code, minutes):
    row = board()
    p = Provider(f"lever:{row.id}", error)
    service = scheduler(row, p)
    result = service.run([], [row])[0]
    assert result["status"] == "failed" and not result["coverage_complete"]
    assert result["error_code"] == code
    assert result["next_eligible_at"] == (NOW + timedelta(minutes=minutes)).isoformat()
    assert service.run([], [row])[0]["status"] == "skipped_not_due"
    assert p.calls == 1
    assert "secret-payload" not in repr(SourceRunRepository().list_runs(p.source_type))


def test_malformed_siblings_degrade_coverage(db):
    row = board()
    result = scheduler(row, Provider(f"lever:{row.id}", skipped=1)).run([], [row])[0]
    assert result["status"] == "partial" and not result["coverage_complete"]
    assert result["error_code"] == "degraded_records"


def test_setup_failure_does_not_block_other_provider(db):
    def broken():
        raise ValueError("secret")
    configs = [ProviderConfig("jooble", broken), ProviderConfig("adzuna", lambda: Provider("adzuna"))]
    result = SourceScheduleService(clock=Clock()).run(configs, [])
    assert result[0]["error_code"] == "provider_setup_failed"
    assert result[1]["status"] == "success"


def test_claim_first_worker_blocks_second_and_stale_recovered(db):
    repo = SourceRunRepository()
    first, _ = repo.acquire("jooble", "jooble", None, NOW)
    assert first
    assert repo.acquire("jooble", "jooble", None, NOW)[1] == "skipped_claimed_elsewhere"
    later = NOW + timedelta(hours=1)
    second, _ = repo.acquire("jooble", "jooble", None, later)
    assert second and second != first
    outcome = SourceIngestionResult("jooble")
    assert not repo.finish("jooble", first, later, outcome, False, later + timedelta(days=1))
    assert repo.finish("jooble", second, later, outcome, False, later + timedelta(days=1))
    assert {r["status"] for r in repo.list_runs("jooble")} == {"expired", "success"}


def test_parallel_sqlite_claims_only_one_owner(db):
    def acquire(_):
        return SourceRunRepository().acquire("jooble", "jooble", None, NOW)[0]
    with ThreadPoolExecutor(max_workers=2) as workers:
        ids = list(workers.map(acquire, [1, 2]))
    assert sum(value is not None for value in ids) == 1


def test_renewal_fenced_and_completion_releases(db):
    repo = SourceRunRepository()
    run, _ = repo.acquire("jooble", "jooble", None, NOW)
    assert not repo.renew("jooble", "other", NOW)
    assert repo.renew("jooble", run, NOW + timedelta(minutes=50))
    assert repo.acquire("jooble", "jooble", None, NOW + timedelta(minutes=70))[0] is None
    end = NOW + timedelta(minutes=80)
    assert repo.finish("jooble", run, end, SourceIngestionResult("jooble"), False, end + timedelta(days=1))
    with database.get_connection() as conn:
        assert conn.execute("SELECT active_run_id FROM source_ingestion_state").fetchone()[0] is None


def test_stale_worker_discards_fetched_results(db):
    from models.job import Job
    row, clock = board(), Clock()
    identity = f"lever:{row.id}"
    class Slow(Provider):
        def search(self, **kwargs):
            clock.now += timedelta(hours=2)
            SourceRunRepository().acquire(identity, "lever", row.id, clock.now)
            return [Job("one", "text", "https://jobs.lever.co/acme/one", title="Engineer")]
    result = scheduler(row, Slow(identity), clock).run([], [row])[0]
    assert result["status"] == "expired"
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def prepare_absence_job(row):
    from models.job import Job
    from services.job_source_repository import JobSourceRepository
    database.upsert_raw_job(Job("job", "text", "https://jobs.lever.co/acme/job", title="Engineer"))
    JobSourceRepository().add_source("job", f"{row.source_type}:{row.id}")
    with database.get_connection() as conn:
        conn.execute("UPDATE job_sources SET last_seen_at=?", ((NOW - timedelta(days=40)).isoformat(),))


def complete(row, when, status="success", coverage=True):
    identity = f"{row.source_type}:{row.id}"
    repo = SourceRunRepository()
    run, _ = repo.acquire(identity, row.source_type, row.id, when)
    assert run
    result = SourceIngestionResult(identity, status=status)
    assert repo.finish(identity, run, when, result, coverage, when + timedelta(hours=6))


def test_archive_requires_repeated_complete_absences_and_age(db):
    row = board()
    prepare_absence_job(row)
    complete(row, NOW - timedelta(hours=6))
    assert JobArchiveService().archive_stale_global_jobs(now=NOW) == 0
    complete(row, NOW)
    assert JobArchiveService().archive_stale_global_jobs(now=NOW) == 1


@pytest.mark.parametrize("condition", ["failed", "partial", "disabled", "stale", "recent_seen", "personal", "active"])
def test_unsafe_absence_never_archives(db, condition):
    row = board()
    prepare_absence_job(row)
    complete(row, NOW - timedelta(hours=12))
    complete(row, NOW - timedelta(hours=6))
    if condition in {"failed", "partial"}:
        complete(row, NOW, condition, False)
    with database.get_connection() as conn:
        if condition == "disabled":
            conn.execute("UPDATE company_job_sources SET enabled=0")
        elif condition == "recent_seen":
            conn.execute("UPDATE job_sources SET last_seen_at=?", (NOW.isoformat(),))
    if condition == "personal":
        from services.user_repository import UserRepository
        from services.job_source_repository import JobSourceRepository
        user = UserRepository().create("private@example.test", "Private")
        JobSourceRepository().add_source("job", "manual", user.id)
    if condition == "active":
        SourceRunRepository().acquire(f"lever:{row.id}", "lever", row.id, NOW)
    check_time = NOW + timedelta(days=3) if condition == "stale" else NOW
    assert JobArchiveService().archive_stale_global_jobs(now=check_time) == 0


def test_complete_before_last_seen_is_not_absence(db):
    row = board()
    prepare_absence_job(row)
    complete(row, NOW - timedelta(days=50))
    complete(row, NOW)
    assert JobArchiveService().archive_stale_global_jobs(now=NOW) == 0


def test_schema_idempotent_server_only_rls(db, monkeypatch):
    with database.get_connection() as conn:
        create_source_run_schema(conn)
        create_source_run_schema(conn)
    statements = []
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    create_source_run_schema(SimpleNamespace(execute=lambda sql: statements.append(sql)))
    assert "ALTER TABLE source_ingestion_runs ENABLE ROW LEVEL SECURITY" in statements
    assert "ALTER TABLE source_ingestion_state ENABLE ROW LEVEL SECURITY" in statements
    assert not any("CREATE POLICY" in s for s in statements)


def test_postgres_adapter_claim_finish_parity(db, monkeypatch):
    import services.source_run_repository as module
    original = database.get_connection
    recorded = []
    class Driver:
        def __init__(self, conn):
            self.conn = conn
        def execute(self, sql, params=()):
            recorded.append(sql)
            return self.conn.execute(sql.replace("%s", "?"), params)
    @contextmanager
    def connection():
        with original() as conn:
            yield database.PostgresConnectionAdapter(Driver(conn))
    monkeypatch.setattr(module, "get_connection", connection)
    repo = SourceRunRepository()
    run, _ = repo.acquire("adzuna", "adzuna", None, NOW)
    assert run and repo.acquire("adzuna", "adzuna", None, NOW)[0] is None
    assert repo.finish("adzuna", run, NOW, SourceIngestionResult("adzuna"), False, NOW + timedelta(days=1))
    assert repo.list_runs("adzuna")[0]["status"] == "success"
    assert any("%s" in s for s in recorded)


def test_actual_connectors_report_complete_or_degraded(db):
    rows = [board("lever"), board("ashby")]
    class HTTP:
        def get_json(self, url, **kwargs):
            return [] if "lever" in url else {"apiVersion": "1", "jobs": [{}]}
    service = SourceScheduleService(clock=Clock(), factories=employer_provider_factories(http_factory=HTTP))
    result = service.run([], rows)
    assert result[0]["coverage_complete"] is True
    assert result[1]["status"] == "partial" and not result[1]["coverage_complete"]


def test_no_candidate_or_payload_fields_in_run_schema(db):
    row = board()
    scheduler(row, Provider(f"lever:{row.id}")).run([], [row])
    run = SourceRunRepository().list_runs(f"lever:{row.id}")[0]
    assert not any(key in run for key in ("candidate_id", "user_id", "url", "payload", "token", "watchlist"))


def test_zero_policy_rejected():
    with pytest.raises(ValueError):
        SourceScheduleService(policy=SchedulePolicy(failure_minutes=0))


def test_many_monitoring_candidates_share_one_registry_fetch(db):
    from models.candidate import Candidate
    from services.candidate_repository import CandidateRepository
    row = board()
    for i in range(3):
        candidate_id = f"private-{i}"
        CandidateRepository().save(Candidate(id=candidate_id, name="Name", current_role="",
                                            current_level="", professional_summary=""))
        with database.get_connection() as conn:
            conn.execute("""INSERT INTO candidate_monitored_companies
                (candidate_id,company_id,active,created_at,updated_at) VALUES (?,?,1,?,?)""",
                (candidate_id, row.company_id, NOW.isoformat(), NOW.isoformat()))
    p = Provider(f"lever:{row.id}")
    service = scheduler(row, p)
    results = service.run(globals=[])
    assert len(results) == 1 and p.calls == 1
    assert "private-" not in repr(SourceRunRepository().list_runs(p.source_type))


def test_reappearance_reactivates_after_evidence_archive(db):
    row = board()
    prepare_absence_job(row)
    complete(row, NOW - timedelta(hours=6))
    complete(row, NOW)
    archive = JobArchiveService()
    assert archive.archive_stale_global_jobs(now=NOW) == 1
    with database.get_connection() as conn:
        conn.execute("UPDATE job_sources SET last_seen_at=?", ((NOW + timedelta(hours=1)).isoformat(),))
    assert archive.reactivate_seen_global_jobs() == 1


@pytest.mark.parametrize("systemic", [False, True])
def test_cli_structured_summary_and_exit_policy(monkeypatch, capsys, systemic):
    import json
    import run_source_scheduler
    monkeypatch.setattr(database, "initialize_database", lambda: None)
    def execute(self):
        if systemic:
            raise RuntimeError("secret-url-or-payload")
        return [{"source_identity": "jooble", "status": "failed", "error_code": "rate_limited"}]
    monkeypatch.setattr(SourceScheduleService, "run", execute)
    monkeypatch.setattr(JobArchiveService, "archive_stale_global_jobs", lambda self: 0)
    assert run_source_scheduler.main() == (1 if systemic else 0)
    printed = capsys.readouterr().out
    assert "secret-url-or-payload" not in printed
    assert json.loads(printed)["status"] == ("failed" if systemic else "completed")
