from __future__ import annotations

from contextlib import contextmanager

import pytest

import services.career_objective_repository as objective_module
import services.career_update_repository as update_module
from models.career_objective import CareerObjective
from models.career_update import CareerUpdate
from services.career_objective_repository import (
    CareerObjectiveRepository,
)
from services.career_update_repository import CareerUpdateRepository


class FakeCursor:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class FakeConnection:
    def __init__(self, *, rowcount):
        self.rowcount = rowcount
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))
        return FakeCursor(self.rowcount)


def _patch_connection(monkeypatch, module, connection):
    @contextmanager
    def fake_get_connection():
        yield connection

    monkeypatch.setattr(
        module,
        "get_connection",
        fake_get_connection,
    )


def test_objective_upsert_requires_same_candidate(
    monkeypatch,
):
    connection = FakeConnection(rowcount=1)
    _patch_connection(
        monkeypatch,
        objective_module,
        connection,
    )
    repository = CareerObjectiveRepository.__new__(
        CareerObjectiveRepository
    )

    repository.save(
        CareerObjective(
            id="objective-a",
            candidate_id="candidate-a",
            title="Target role",
            description="Direction",
            active=False,
        )
    )

    sql, params = connection.calls[0]

    assert (
        "candidate_career_objectives.candidate_id "
        "= excluded.candidate_id"
        in sql
    )
    assert params[1] == "candidate-a"


def test_objective_rejects_id_owned_by_other_candidate(
    monkeypatch,
):
    connection = FakeConnection(rowcount=0)
    _patch_connection(
        monkeypatch,
        objective_module,
        connection,
    )
    repository = CareerObjectiveRepository.__new__(
        CareerObjectiveRepository
    )

    with pytest.raises(
        ValueError,
        match="not found for candidate",
    ):
        repository.save(
            CareerObjective(
                id="objective-a",
                candidate_id="candidate-b",
                title="Injected target",
                description="Injected direction",
                active=False,
            )
        )


def test_career_update_upsert_requires_same_candidate(
    monkeypatch,
):
    connection = FakeConnection(rowcount=1)
    _patch_connection(
        monkeypatch,
        update_module,
        connection,
    )
    repository = CareerUpdateRepository.__new__(
        CareerUpdateRepository
    )

    repository.save(
        CareerUpdate(
            id="update-a",
            candidate_id="candidate-a",
            update_type="new_skill",
            description="SQL",
        )
    )

    sql, params = connection.calls[0]

    assert (
        "candidate_career_updates.candidate_id "
        "= excluded.candidate_id"
        in sql
    )
    assert params[1] == "candidate-a"


def test_career_update_rejects_id_owned_by_other_candidate(
    monkeypatch,
):
    connection = FakeConnection(rowcount=0)
    _patch_connection(
        monkeypatch,
        update_module,
        connection,
    )
    repository = CareerUpdateRepository.__new__(
        CareerUpdateRepository
    )

    with pytest.raises(
        ValueError,
        match="not found for candidate",
    ):
        repository.save(
            CareerUpdate(
                id="update-a",
                candidate_id="candidate-b",
                update_type="new_skill",
                description="Injected",
            )
        )


def test_career_update_delete_is_candidate_scoped(
    monkeypatch,
):
    connection = FakeConnection(rowcount=0)
    _patch_connection(
        monkeypatch,
        update_module,
        connection,
    )
    repository = CareerUpdateRepository.__new__(
        CareerUpdateRepository
    )

    deleted = repository.delete(
        "update-a",
        "candidate-b",
    )

    sql, params = connection.calls[0]

    assert "id = ? AND candidate_id = ?" in sql
    assert params == (
        "update-a",
        "candidate-b",
    )
    assert deleted is False
