from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from services import database
from services.database import create_preparation_generation_claim_schema
from services.prepare_application_factory import (
    build_production_prepare_application_service,
)
from services.preparation_generation_claim_repository import (
    PreparationGenerationClaimRepository,
)
import services.prepare_application_factory as factory_module
import services.preparation_generation_claim_repository as repository_module


@pytest.fixture
def claim_repository(tmp_path, monkeypatch):
    path = tmp_path / "generation-claims.db"

    @contextmanager
    def connect():
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    with connect() as connection:
        connection.execute("CREATE TABLE candidates (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO candidates VALUES (?)",
            [("candidate-a",), ("candidate-b",)],
        )
        connection.executemany(
            "INSERT INTO jobs VALUES (?)",
            [("job-1",), ("job-2",)],
        )
        create_preparation_generation_claim_schema(connection)
    monkeypatch.setattr(repository_module, "get_connection", connect)
    return PreparationGenerationClaimRepository(), connect


def _acquire(repository, token, *, candidate="candidate-a", job="job-1", signature="sig-1"):
    return repository.acquire(
        candidate_id=candidate,
        job_id=job,
        application_context_signature=signature,
        claim_token=token,
        ttl_seconds=900,
    )


def test_only_one_active_claimant_for_same_semantic_request(claim_repository):
    repository, _ = claim_repository
    assert _acquire(repository, "token-a")
    assert not _acquire(repository, "token-b")


@pytest.mark.parametrize(
    "changes",
    [
        {"candidate": "candidate-b"},
        {"job": "job-2"},
        {"signature": "sig-2"},
    ],
)
def test_different_claim_scope_can_proceed_independently(claim_repository, changes):
    repository, _ = claim_repository
    assert _acquire(repository, "token-a")
    assert _acquire(repository, "token-b", **changes)


def test_only_owner_can_release_claim(claim_repository):
    repository, _ = claim_repository
    assert _acquire(repository, "token-a")
    assert not repository.release(
        candidate_id="candidate-a",
        job_id="job-1",
        application_context_signature="sig-1",
        claim_token="token-b",
    )
    assert not _acquire(repository, "token-b")
    assert repository.release(
        candidate_id="candidate-a",
        job_id="job-1",
        application_context_signature="sig-1",
        claim_token="token-a",
    )
    assert _acquire(repository, "token-b")


def test_expired_claim_can_be_reclaimed(claim_repository):
    repository, connect = claim_repository
    assert _acquire(repository, "token-a")
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with connect() as connection:
        connection.execute(
            "UPDATE candidate_preparation_generation_claims "
            "SET claim_expires_at = ?",
            (expired,),
        )
    assert _acquire(repository, "token-b")


def test_claim_schema_enables_postgres_rls_without_grants(monkeypatch):
    class Connection:
        def __init__(self):
            self.sql = []

        def execute(self, sql, *_args):
            self.sql.append(" ".join(sql.split()))
            return self

    monkeypatch.setattr(database, "is_postgres", lambda: True)
    connection = Connection()
    create_preparation_generation_claim_schema(connection)
    sql = "\n".join(connection.sql).casefold()
    assert (
        "alter table candidate_preparation_generation_claims "
        "enable row level security"
    ) in sql
    assert "create policy" not in sql
    assert " grant " not in f" {sql} "


def test_production_factory_construction_is_transport_inert(monkeypatch):
    calls = []

    class InertClient:
        def generate(self, _prompt):
            calls.append("generate")
            raise AssertionError("Factory construction must not generate.")

    monkeypatch.setattr(
        "services.ai.openai_client.OpenAIClient", lambda: InertClient()
    )
    service = build_production_prepare_application_service()
    assert calls == []
    assert isinstance(
        service.claim_repository, PreparationGenerationClaimRepository
    )


def test_production_factory_import_has_no_generation_side_effect():
    source = Path("services/prepare_application_factory.py").read_text(
        encoding="utf-8"
    )
    assert ".generate(" not in source
    assert "responses.create" not in source


def test_opportunities_wires_factory_but_only_button_requests_action():
    source = Path("pages/1_Opportunities.py").read_text(encoding="utf-8")
    assert "build_production_prepare_application_service()" in source
    assert "action_requested=prepare_requested" in source
    assert "Generates a tailored CV for this opportunity using AI." in source
    assert "preparation_service.prepare(" not in source


def test_missing_configuration_message_does_not_expose_secret_name():
    source = Path("pages/1_Opportunities.py").read_text(encoding="utf-8")
    assert "Tailored CV generation is currently unavailable." in source
    assert "OPENAI_API_KEY" not in source
