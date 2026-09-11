from __future__ import annotations

from contextlib import contextmanager

import pytest

import services.candidate_onboarding_repository as repository_module
from models.work_experience import WorkExperience
from services.candidate_onboarding_repository import (
    CandidateOnboardingRepository,
)


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


def _repository(monkeypatch, connection):
    @contextmanager
    def fake_get_connection():
        yield connection

    monkeypatch.setattr(
        repository_module,
        "get_connection",
        fake_get_connection,
    )

    return CandidateOnboardingRepository.__new__(
        CandidateOnboardingRepository
    )


def _experience(candidate_id):
    return WorkExperience(
        id="experience-a",
        candidate_id=candidate_id,
        company="Example",
        start_date="2025-01",
        end_date=None,
        career_story="Story",
        day_to_day_narrative="Daily work",
    )


def test_update_scopes_experience_to_candidate(
    monkeypatch,
):
    connection = FakeConnection(rowcount=1)
    repository = _repository(monkeypatch, connection)

    repository.update_work_experience(
        _experience("candidate-a")
    )

    sql, params = connection.calls[0]

    assert "id = ? AND candidate_id = ?" in sql
    assert params[-2:] == (
        "experience-a",
        "candidate-a",
    )


def test_update_rejects_experience_owned_by_other_candidate(
    monkeypatch,
):
    repository = _repository(
        monkeypatch,
        FakeConnection(rowcount=0),
    )

    with pytest.raises(
        ValueError,
        match="not found for candidate",
    ):
        repository.update_work_experience(
            _experience("candidate-b")
        )


def test_delete_scopes_experience_to_candidate(
    monkeypatch,
):
    connection = FakeConnection(rowcount=1)
    repository = _repository(monkeypatch, connection)

    repository.delete_work_experience(
        "experience-a",
        "candidate-a",
    )

    sql, params = connection.calls[0]

    assert "id = ? AND candidate_id = ?" in sql
    assert params == (
        "experience-a",
        "candidate-a",
    )


def test_delete_rejects_experience_owned_by_other_candidate(
    monkeypatch,
):
    repository = _repository(
        monkeypatch,
        FakeConnection(rowcount=0),
    )

    with pytest.raises(
        ValueError,
        match="not found for candidate",
    ):
        repository.delete_work_experience(
            "experience-a",
            "candidate-b",
        )
