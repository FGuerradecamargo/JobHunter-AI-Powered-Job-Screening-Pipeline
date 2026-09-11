from __future__ import annotations

from contextlib import contextmanager

import pytest

import services.objective_profile_repository as repository_module
from models.candidate import Candidate
from models.career_objective import CareerObjective
from models.objective_profile import ObjectiveProfile
from services.objective_profile_generation_service import (
    ObjectiveProfileGenerationService,
)
from services.objective_profile_repository import (
    ObjectiveProfileRepository,
)


class FakeCursor:
    def __init__(self, *, row=None, rowcount=0):
        self._row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, *, upsert_rowcount=1):
        self.upsert_rowcount = upsert_rowcount
        self.calls = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))

        if normalized.startswith("SELECT created_at"):
            return FakeCursor(row=None)

        if normalized.startswith(
            "INSERT INTO candidate_objective_profiles"
        ):
            return FakeCursor(
                rowcount=self.upsert_rowcount
            )

        if normalized.startswith("SELECT profile_json"):
            return FakeCursor(row=None)

        raise AssertionError(
            f"Unexpected objective profile query: {normalized}"
        )


def _repository(monkeypatch, connection):
    @contextmanager
    def fake_get_connection():
        yield connection

    monkeypatch.setattr(
        repository_module,
        "get_connection",
        fake_get_connection,
    )

    return ObjectiveProfileRepository.__new__(
        ObjectiveProfileRepository
    )


def test_objective_profile_upsert_cannot_transfer_candidate(
    monkeypatch,
):
    connection = FakeConnection(upsert_rowcount=0)
    repository = _repository(monkeypatch, connection)

    with pytest.raises(
        ValueError,
        match="not found for candidate",
    ):
        repository.save(
            ObjectiveProfile(
                candidate_id="candidate-b",
                objective_id="objective-a",
            )
        )

    select_sql, select_params = connection.calls[0]
    upsert_sql, _ = connection.calls[1]

    assert "objective_id = ? AND candidate_id = ?" in select_sql
    assert select_params == (
        "objective-a",
        "candidate-b",
    )
    assert "candidate_id = excluded.candidate_id" in upsert_sql
    assert "candidate_id = excluded.candidate_id," not in upsert_sql


def test_objective_profile_read_is_candidate_scoped(
    monkeypatch,
):
    connection = FakeConnection()
    repository = _repository(monkeypatch, connection)

    assert (
        repository.get_for_objective(
            "objective-a",
            "candidate-b",
        )
        is None
    )

    sql, params = connection.calls[0]

    assert "objective_id = ? AND candidate_id = ?" in sql
    assert params == (
        "objective-a",
        "candidate-b",
    )


class NoCallLLM:
    def generate(self, prompt):
        raise AssertionError("LLM must not be called")


class NoCallRepository:
    def save(self, profile):
        raise AssertionError("Repository must not be called")


def test_generation_rejects_objective_from_other_candidate():
    service = ObjectiveProfileGenerationService(
        llm_client=NoCallLLM(),
        repository=NoCallRepository(),
    )

    with pytest.raises(
        PermissionError,
        match="does not belong to candidate",
    ):
        service.generate(
            candidate=Candidate(
                id="candidate-a",
                name="Candidate A",
                current_role="Role",
                current_level="mid",
                professional_summary="Summary",
            ),
            objective=CareerObjective(
                id="objective-b",
                candidate_id="candidate-b",
                title="Target",
                description="Direction",
            ),
        )
