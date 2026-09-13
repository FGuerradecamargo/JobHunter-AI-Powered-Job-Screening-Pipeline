from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from pathlib import Path

import pytest

import services.application_lifecycle_repository as repository_module
from services.application_lifecycle_repository import ApplicationLifecycleRepository
from services.application_lifecycle_service import ApplicationLifecycleService
from services.application_lifecycle_ui import (
    handle_mark_applied_action,
    handle_user_rejected_action,
)


class FakeRepository:
    def __init__(self, row=None):
        self.row = dict(row) if row is not None else None
        self.applied_calls = []
        self.rejected_calls = []

    def get(self, candidate_id, job_id):
        if self.row is None:
            return None
        if (candidate_id, job_id) != (
            self.row["candidate_id"],
            self.row["job_id"],
        ):
            return None
        return dict(self.row)

    def mark_applied(self, candidate_id, job_id, applied_at):
        self.applied_calls.append((candidate_id, job_id, applied_at))
        if self.get(candidate_id, job_id) is None:
            return None
        self.row.update(
            status="applied",
            opportunity_state="applied",
            applied_at=self.row.get("applied_at") or applied_at,
        )
        return dict(self.row)

    def mark_user_rejected(self, candidate_id, job_id, updated_at):
        self.rejected_calls.append((candidate_id, job_id, updated_at))
        if self.get(candidate_id, job_id) is None:
            return None
        self.row.update(
            status="user_rejected",
            opportunity_state="user_rejected",
        )
        return dict(self.row)


def _row(status="in_review", applied_at=None):
    return {
        "candidate_id": "candidate-a",
        "job_id": "job-1",
        "status": status,
        "opportunity_state": "active" if status == "in_review" else status,
        "applied_at": applied_at,
        "rejected_at": None,
    }


def _service(repository):
    return ApplicationLifecycleService(
        repository=repository,
        clock=lambda: "2026-09-12T10:30:00+00:00",
    )


def test_explicit_mark_applied_succeeds_without_prepared_cv():
    repository = FakeRepository(_row())

    result = _service(repository).mark_applied("candidate-a", "job-1")

    assert result.status == "applied"
    assert result.opportunity_state == "applied"
    assert result.applied_at == "2026-09-12T10:30:00+00:00"
    assert result.succeeded


def test_repeated_mark_applied_is_idempotent_and_keeps_timestamp():
    repository = FakeRepository(_row())
    service = _service(repository)

    first = service.mark_applied("candidate-a", "job-1")
    second = service.mark_applied("candidate-a", "job-1")

    assert first.status == "applied"
    assert second.status == "already_applied"
    assert second.applied_at == first.applied_at
    assert len(repository.applied_calls) == 1


def test_candidate_mismatch_is_rejected_without_update():
    repository = FakeRepository(_row())

    result = _service(repository).mark_applied("candidate-b", "job-1")

    assert result.status == "failed"
    assert result.error_code == "candidate_job_not_found"
    assert repository.applied_calls == []


def test_missing_candidate_job_is_rejected():
    repository = FakeRepository()

    result = _service(repository).mark_applied("candidate-a", "missing")

    assert result.status == "failed"
    assert result.error_code == "candidate_job_not_found"


def test_user_rejected_to_applied_requires_explicit_mark_action():
    repository = FakeRepository(_row("user_rejected"))
    service = _service(repository)

    no_action = handle_mark_applied_action(
        action_requested=False,
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_service=service,
    )
    result = handle_mark_applied_action(
        action_requested=True,
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_service=service,
    )

    assert no_action is None
    assert result is not None and result.status == "applied"
    assert len(repository.applied_calls) == 1


@pytest.mark.parametrize(
    "later_status",
    [
        "rejected_before_interview",
        "in_process",
        "rejected_after_interview",
        "offer",
    ],
)
def test_later_outcome_cannot_be_reset_to_applied(later_status):
    repository = FakeRepository(_row(later_status, "original-applied-at"))

    result = _service(repository).mark_applied("candidate-a", "job-1")

    assert result.status == "failed"
    assert result.error_code == "invalid_transition"
    assert result.applied_at == "original-applied-at"
    assert repository.applied_calls == []


def test_do_not_apply_is_an_explicit_candidate_scoped_transition():
    repository = FakeRepository(_row())

    result = handle_user_rejected_action(
        action_requested=True,
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_service=_service(repository),
    )

    assert result is not None
    assert result.status == "user_rejected"
    assert result.opportunity_state == "user_rejected"


def test_applied_cannot_be_downgraded_to_user_rejected():
    repository = FakeRepository(_row("applied", "original-applied-at"))

    result = _service(repository).mark_user_rejected("candidate-a", "job-1")

    assert result.status == "failed"
    assert result.error_code == "invalid_transition"
    assert repository.rejected_calls == []


@pytest.mark.parametrize(
    "passive_action",
    ["page_render", "prepare_application", "cv_download", "open_job_url"],
)
def test_passive_ui_actions_never_mark_applied(passive_action):
    repository = FakeRepository(_row())

    result = handle_mark_applied_action(
        action_requested=False,
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_service=_service(repository),
    )

    assert passive_action
    assert result is None
    assert repository.applied_calls == []


def _install_sqlite_connection(monkeypatch, database_path):
    @contextmanager
    def get_connection():
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    monkeypatch.setattr(repository_module, "get_connection", get_connection)


def _create_schema(database_path):
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE candidate_job_analyses (
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            status TEXT NOT NULL,
            opportunity_state TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            tailored_cv_json TEXT,
            notes TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            applied_at TEXT,
            rejected_at TEXT,
            PRIMARY KEY (candidate_id, job_id)
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO candidate_job_analyses VALUES (
            ?, ?, 'in_review', 'active', ?, ?, ?, 'old', NULL, NULL
        )
        """,
        [
            ("candidate-a", "job-1", '{"fit": 90}', '{"cv": "a"}', "keep a"),
            ("candidate-b", "job-1", '{"fit": 40}', '{"cv": "b"}', "keep b"),
        ],
    )
    connection.commit()
    connection.close()


def test_repository_preserves_analysis_cv_and_other_candidate(
    monkeypatch,
    tmp_path: Path,
):
    database_path = tmp_path / "lifecycle.db"
    _create_schema(database_path)
    _install_sqlite_connection(monkeypatch, database_path)

    result = _service(ApplicationLifecycleRepository()).mark_applied(
        "candidate-a",
        "job-1",
    )

    connection = sqlite3.connect(database_path)
    rows = connection.execute(
        """
        SELECT candidate_id, status, opportunity_state, analysis_json,
               tailored_cv_json, notes, applied_at
        FROM candidate_job_analyses ORDER BY candidate_id
        """
    ).fetchall()
    connection.close()

    assert result.status == "applied"
    assert rows[0] == (
        "candidate-a",
        "applied",
        "applied",
        '{"fit": 90}',
        '{"cv": "a"}',
        "keep a",
        "2026-09-12T10:30:00+00:00",
    )
    assert rows[1][1:] == (
        "in_review",
        "active",
        '{"fit": 40}',
        '{"cv": "b"}',
        "keep b",
        None,
    )


def test_opportunities_ui_uses_lifecycle_boundary_and_clear_applied_state():
    source = Path("pages/1_Opportunities.py").read_text(encoding="utf-8")

    assert "handle_mark_applied_action(" in source
    assert "Opportunity marked as applied." in source
    assert "update_candidate_job_status" not in source


def test_lifecycle_has_no_ai_or_generation_dependency():
    paths = [
        Path("services/application_lifecycle_service.py"),
        Path("services/application_lifecycle_repository.py"),
        Path("services/application_lifecycle_ui.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "openai" not in source.lower()
    assert "generator" not in source.lower()
    assert "prepare_application" not in source
