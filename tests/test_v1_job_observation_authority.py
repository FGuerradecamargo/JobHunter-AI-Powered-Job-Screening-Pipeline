from dataclasses import replace

import pytest

from services import database
from services.job_import_service import JobImportService
from services.user_repository import UserRepository
from services.job_source_repository import JobSourceRepository
from tests.test_source_v2_foundation import job, FakeProvider


def ingest(item, source="alpha", user=None):
    return JobImportService().import_jobs(FakeProvider(source, [item]), source, "", "", user_id=user)


def stored(identifier):
    with database.get_connection() as connection:
        return dict(connection.execute("SELECT * FROM jobs WHERE id = ?", (identifier,)).fetchone())


def test_private_longer_observation_cannot_replace_public_content():
    user = UserRepository().create("fixture@example.test", "Fixture")
    original = job()
    ingest(original)
    ingest(replace(original, raw_text="private text " * 50, description="private evidence"), user=user.id)
    assert stored(original.id)["raw_text"] == original.raw_text
    assert stored(original.id)["description"] == original.description


def test_public_authority_is_not_longest_text():
    original = job()
    ingest(original)
    ingest(replace(original, id="beta:1", raw_text="longer " * 50, description="Other source"), "beta")
    assert stored(original.id)["raw_text"] == original.raw_text


def test_legacy_raw_write_has_no_overwrite_authority():
    original = job()
    database.upsert_raw_job(original)
    database.upsert_raw_job(replace(original, raw_text="longer " * 50))
    assert stored(original.id)["raw_text"] == original.raw_text


@pytest.mark.parametrize("reverse", [False, True])
def test_private_collision_order_never_shares_private_payload(reverse):
    users = [UserRepository().create(f"{i}@example.test", "Fixture").id for i in range(2)]
    for i in reversed(range(2)) if reverse else range(2):
        ingest(replace(job(), raw_text=f"private-{i}"), "manual", users[i])
    observations = [JobSourceRepository().list_observations_for_user(u)[0] for u in users]
    assert observations[0]["job_id"] != observations[1]["job_id"]
    for i, observation in enumerate(observations):
        assert stored(observation["job_id"])["raw_text"] == f"private-{i}"


@pytest.mark.parametrize("reverse", [False, True])
def test_public_authority_is_order_independent(reverse):
    items = [(job(), "alpha"), (replace(job(), id="beta:1", raw_text="beta " * 30), "beta")]
    for item, source in reversed(items) if reverse else items:
        ingest(item, source)
    with database.get_connection() as connection:
        rows = connection.execute("SELECT * FROM jobs").fetchall()
    assert len(rows) == 1
    assert rows[0]["raw_text"] == job().raw_text


@pytest.mark.parametrize("change", [dict(company="Other"), dict(title="Other"), dict(location="Other"), dict(url="https://jobs.example/other")])
def test_provider_id_collision_requires_consistent_identity(change):
    ingest(job())
    assert ingest(replace(job(), **change))["created"] == 1
    assert stored(job().id)["company"] == job().company


def test_public_reobservation_can_correct_to_shorter_text():
    ingest(job())
    assert ingest(replace(job(), raw_text="Short correction"))["updated"] == 1
    assert stored(job().id)["raw_text"] == "Short correction"
    assert ingest(replace(job(), raw_text="Short correction"))["unchanged"] == 1


def test_two_private_owners_can_reference_public_job_without_content_authority():
    ingest(job())
    users = [UserRepository().create(f"{i}@example.test", "Fixture").id for i in range(2)]
    for user in users:
        ingest(replace(job(), raw_text=user * 20), "manual", user)
        assert JobSourceRepository().list_by_user(user) == [job().id]
        assert len(JobSourceRepository().list_observations_for_user(user)) == 1
    with database.get_connection() as connection:
        connection.execute("DELETE FROM job_sources WHERE user_id = ?", (users[0],))
    assert JobSourceRepository().list_by_user(users[1]) == [job().id]
    assert stored(job().id)["raw_text"] == job().raw_text


def test_failed_provenance_write_rolls_back_job_and_observation(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("fixture")
    monkeypatch.setattr(JobSourceRepository, "add_source", fail)
    with pytest.raises(RuntimeError):
        ingest(job())
    with database.get_connection() as connection:
        for table in ("jobs", "job_observations", "job_content_authority"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_description_fetch_requires_public_authority_and_matching_url():
    database.upsert_raw_job(job())
    database.update_shared_job_analysis_data(replace(job(), description="unproven"))
    assert stored(job().id)["description"] == job().description
    public = replace(job(), id="new", url="https://jobs.example/new")
    ingest(public)
    database.update_shared_job_analysis_data(replace(public, id="alpha:new", url="https://other.example", description="wrong"))
    assert stored("alpha:new")["description"] == public.description
    database.update_shared_job_analysis_data(replace(public, id="alpha:new", description="Fetched public text"))
    assert stored("alpha:new")["description"] == "Fetched public text"


def test_migration_is_additive_idempotent_and_does_not_invent_legacy_authority():
    database.upsert_raw_job(job())
    with database.get_connection() as connection:
        database.create_job_observation_schema(connection)
        database.create_job_observation_schema(connection)
        assert connection.execute("SELECT COUNT(*) FROM job_content_authority").fetchone()[0] == 0
    assert stored(job().id)["raw_text"] == job().raw_text


def test_retired_global_recommendation_import_cannot_bootstrap_or_write(monkeypatch):
    import sync_database
    def forbidden(*args, **kwargs):
        pytest.fail("Retired command accessed database")
    monkeypatch.setattr(database, "get_connection", forbidden)
    monkeypatch.setattr(database, "initialize_database", forbidden)
    with pytest.raises(SystemExit, match="disabled"):
        sync_database.main()


def test_ingestion_to_official_job_profile_preserves_authority_and_history():
    from models.profile_interpretation import JobProfileDraft, InterpretedJobNeed, InterpretationAuthority
    from models.hiring_case import RequirementImportance
    from services.profile_interpretation_service import ProfileInterpretationService
    from services.profile_snapshot_repository import ProfileSnapshotRepository
    class Interpreter:
        def build_job_profile(self, *, hard_facts, previous_profile):
            return JobProfileDraft(needs=(InterpretedJobNeed("n", "Build tools", RequirementImportance.CORE,
                InterpretationAuthority.EXPLICIT, (hard_facts.fact_refs[0],)),))
    ingest(job())
    source = JobSourceRepository()
    snapshots = ProfileSnapshotRepository()
    service = ProfileInterpretationService(snapshots, Interpreter())
    first = service.job_profile_from_observation(job_id=job().id, source_repository=source)
    user = UserRepository().create("private@example.test", "Fixture")
    ingest(replace(job(), description="private " * 30), "manual", user.id)
    assert service.job_profile_from_observation(job_id=job().id, source_repository=source) == first
    ingest(replace(job(), description="Changed public requirement"))
    second = service.job_profile_from_observation(job_id=job().id, source_repository=source)
    assert second.profile_version == first.profile_version + 1
    assert second.job_signature != first.job_signature
    assert snapshots.job_for_signature(job().id, first.job_signature, first.schema_version) == first


def test_private_job_source_cannot_be_read_as_global_or_by_another_user():
    owner = UserRepository().create("owner@example.test", "Fixture")
    ingest(job(), "manual", owner.id)
    source = JobSourceRepository()
    job_id = source.list_by_user(owner.id)[0]
    for user_id in (None, "other"):
        with pytest.raises(ValueError, match="unavailable"):
            source.load_job_hard_facts(job_id, user_id=user_id)
    facts = source.load_job_hard_facts(job_id, user_id=owner.id)
    assert facts.facts
    assert all(not fact.hard_blocker for fact in facts.facts)
    assert all(fact.requirement_status.value == "unknown" for fact in facts.facts)


def test_gmail_runtime_retry_is_owner_scoped(monkeypatch):
    from types import SimpleNamespace
    from services.gmail_job_processor import GmailJobProcessor
    users = [UserRepository().create(f"gmail{i}@example.test", "Fixture").id for i in range(2)]
    monkeypatch.setattr("services.gmail_job_processor.extract_jobs_from_email", lambda **kw:
        SimpleNamespace(jobs={"collision": replace(job(), raw_text=kw["html"])}, source="linkedin"))
    messages = SimpleNamespace(list_pending=lambda **kw: [{"gmail_message_id": "same-id", "raw_html": kw["user_id"]}],
        mark_processed=lambda **kw: None, mark_failed=lambda **kw: pytest.fail("Unexpected Gmail failure"))
    processor = GmailJobProcessor(gmail_message_repository=messages)
    assert processor.process_pending_messages(users[0]).jobs_created == 1
    assert processor.process_pending_messages(users[1]).jobs_created == 1
    assert processor.process_pending_messages(users[0]).jobs_unchanged == 1
    for user in users:
        observations = JobSourceRepository().list_observations_for_user(user)
        assert len(observations) == 1
        assert stored(observations[0]["job_id"])["raw_text"] == user


def test_postgres_observation_migration_enables_rls_and_revokes_public_roles(monkeypatch):
    statements = []
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    class Connection:
        def execute(self, sql):
            statements.append(sql)
    database.create_job_observation_schema(Connection())
    for table in ("job_observations", "job_content_authority"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"REVOKE ALL ON TABLE {table} FROM PUBLIC" in statements
        assert any(f"REVOKE ALL ON TABLE {table} FROM authenticated" in sql for sql in statements)


def test_board_publication_timestamp_is_serialized_without_losing_provenance():
    from datetime import datetime, timezone
    import json
    from services.job_sources.employer_board import BoardJob
    from dataclasses import asdict
    posted = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ingest(BoardJob(**asdict(job()), published_at=posted))
    with database.get_connection() as connection:
        row = connection.execute("SELECT payload_json FROM job_observations").fetchone()
    assert json.loads(row["payload_json"])["published_at"] == posted.isoformat()


@pytest.mark.parametrize("source", ["gmail", "gmail_linkedin", "manual", "private:note", "user:import"])
def test_private_source_cannot_claim_public_authority(source):
    with pytest.raises(ValueError, match="owner"):
        JobSourceRepository().record_observation(job(), source, trusted_public=True)


def test_public_source_requires_explicit_eligibility():
    with pytest.raises(ValueError, match="eligibility"):
        JobSourceRepository().record_observation(job(), "alpha")


def test_provider_extension_cannot_store_unrecognized_private_metadata():
    from dataclasses import asdict, dataclass
    import json
    from models.job import Job
    @dataclass
    class ExtendedJob(Job):
        candidate_context: str = "must not become global"
    ingest(ExtendedJob(**asdict(job())))
    with database.get_connection() as connection:
        row = connection.execute("SELECT payload_json FROM job_observations").fetchone()
    assert "candidate_context" not in json.loads(row["payload_json"])
