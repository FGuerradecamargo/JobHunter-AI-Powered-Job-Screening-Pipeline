from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import sqlite3
from pathlib import Path

import pytest

import services.application_outcome_repository as repository_module
from models.application_outcome import ApplicationOutcome
from models.candidate import Candidate
from services.application_outcome_repository import ApplicationOutcomeRepository
from services.application_outcome_service import ApplicationOutcomeService
from services.career_evidence_service import CareerEvidenceService


class FakeOutcomeRepository:
    def __init__(self, *, application_status="applied", outcome=None):
        self.application_status = application_status
        self.outcome = outcome
        self.saved = []

    def get_application(self, candidate_id, job_id):
        if (candidate_id, job_id) != ("candidate-a", "job-1"):
            return None
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "status": self.application_status,
            "opportunity_state": self.application_status,
            "applied_at": "2026-09-12T09:00:00+00:00",
        }

    def get(self, candidate_id, job_id):
        if (candidate_id, job_id) != ("candidate-a", "job-1"):
            return None
        return self.outcome

    def save(self, outcome):
        self.outcome = outcome
        self.saved.append(outcome)
        return outcome


class SequenceClock:
    def __init__(self):
        self.count = 0

    def __call__(self):
        self.count += 1
        return f"2026-09-12T10:00:{self.count:02d}+00:00"


def _service(repository=None, clock=None):
    return ApplicationOutcomeService(
        repository=repository or FakeOutcomeRepository(),
        clock=clock or SequenceClock(),
    )


def _progress_to(service, state):
    result = None
    if state in {"interview", "final_interview", "offer", "accepted", "declined"}:
        result = service.mark_interview("candidate-a", "job-1")
    if state in {"final_interview", "offer", "accepted", "declined"}:
        result = service.mark_final_interview("candidate-a", "job-1")
    if state in {"offer", "accepted", "declined"}:
        result = service.mark_offer("candidate-a", "job-1")
    if state == "accepted":
        result = service.mark_accepted("candidate-a", "job-1")
    if state == "declined":
        result = service.mark_declined("candidate-a", "job-1")
    return result


def test_applied_to_interview_succeeds_without_final_status():
    result = _service().mark_interview("candidate-a", "job-1")

    assert result.status == "updated"
    assert result.interview_stage == "interview"
    assert result.final_status == ""


def test_interview_to_final_interview_succeeds():
    service = _service()
    service.mark_interview("candidate-a", "job-1")

    result = service.mark_final_interview("candidate-a", "job-1")

    assert result.interview_stage == "final_interview"
    assert result.final_status == ""


def test_final_interview_to_offer_does_not_imply_accepted():
    service = _service()
    _progress_to(service, "final_interview")

    result = service.mark_offer("candidate-a", "job-1")

    assert result.final_status == "offer"
    assert result.interview_stage == "final_interview"
    assert result.final_status != "accepted"


@pytest.mark.parametrize("terminal", ["accepted", "declined"])
def test_offer_to_terminal_candidate_decision(terminal):
    service = _service()
    _progress_to(service, "offer")

    result = getattr(service, f"mark_{terminal}")("candidate-a", "job-1")

    assert result.final_status == terminal


@pytest.mark.parametrize(
    ("start", "expected_stage"),
    [("applied", ""), ("interview", "interview"),
     ("final_interview", "final_interview")],
)
def test_rejection_preserves_timing_stage(start, expected_stage):
    service = _service()
    if start != "applied":
        _progress_to(service, start)

    result = service.mark_rejected(
        "candidate-a",
        "job-1",
        rejection_reason="Employer selected another candidate",
    )

    assert result.final_status == "rejected"
    assert result.interview_stage == expected_stage


@pytest.mark.parametrize("start", ["applied", "interview", "final_interview", "offer"])
def test_withdrawal_is_distinct_from_employer_rejection(start):
    service = _service()
    if start != "applied":
        _progress_to(service, start)

    result = service.mark_withdrawn("candidate-a", "job-1")

    assert result.final_status == "withdrawn"
    assert result.final_status != "rejected"


def test_offer_salary_is_optional_and_can_be_recorded():
    service = _service()
    _progress_to(service, "final_interview")

    without_salary = service.mark_offer("candidate-a", "job-1")

    assert without_salary.status == "updated"
    assert service.repository.outcome.offer_salary == ""


def test_offer_preserves_optional_salary_and_currency():
    service = _service()
    _progress_to(service, "final_interview")

    service.mark_offer(
        "candidate-a", "job-1", offer_salary="70000", offer_currency="GBP"
    )

    assert service.repository.outcome.offer_salary == "70000"
    assert service.repository.outcome.offer_currency == "GBP"


@pytest.mark.parametrize("status", ["in_review", "user_rejected"])
def test_non_applied_opportunity_cannot_record_interview(status):
    repository = FakeOutcomeRepository(application_status=status)

    result = _service(repository).mark_interview("candidate-a", "job-1")

    assert result.status == "failed"
    assert result.error_code == "application_not_applied"
    assert repository.saved == []


def test_missing_candidate_job_fails_safely():
    result = _service().mark_interview("candidate-a", "missing")

    assert result.status == "failed"
    assert result.error_code == "candidate_job_not_found"


def test_candidate_cannot_update_another_candidates_outcome():
    repository = FakeOutcomeRepository()

    result = _service(repository).mark_interview("candidate-b", "job-1")

    assert result.status == "failed"
    assert repository.saved == []


def test_identical_transition_is_idempotent_and_preserves_timestamps():
    repository = FakeOutcomeRepository()
    clock = SequenceClock()
    service = _service(repository, clock)

    first = service.mark_interview("candidate-a", "job-1")
    second = service.mark_interview("candidate-a", "job-1")

    assert second.status == "already_current"
    assert second.created_at == first.created_at
    assert second.updated_at == first.updated_at
    assert second.outcome_date == first.outcome_date
    assert len(repository.saved) == 1
    assert clock.count == 2


@pytest.mark.parametrize("terminal", ["rejected", "accepted", "declined", "withdrawn"])
def test_terminal_outcome_cannot_regress(terminal):
    service = _service()
    if terminal in {"accepted", "declined"}:
        _progress_to(service, "offer")
    elif terminal == "rejected":
        service.mark_rejected("candidate-a", "job-1")
    else:
        service.mark_withdrawn("candidate-a", "job-1")
    if terminal in {"accepted", "declined"}:
        getattr(service, f"mark_{terminal}")("candidate-a", "job-1")

    result = service.mark_interview("candidate-a", "job-1")

    assert result.status == "failed"
    assert result.error_code == "invalid_transition"


def test_real_transition_preserves_created_at_and_changes_updated_at():
    service = _service()
    interview = service.mark_interview("candidate-a", "job-1")

    final = service.mark_final_interview("candidate-a", "job-1")

    assert final.created_at == interview.created_at
    assert final.updated_at != interview.updated_at


def test_details_survive_later_transitions_when_not_replaced():
    service = _service()
    service.mark_interview(
        "candidate-a", "job-1", recruiter_feedback="Strong screen"
    )

    service.mark_final_interview("candidate-a", "job-1")

    assert service.repository.outcome.recruiter_feedback == "Strong screen"


def _install_database(monkeypatch, database_path):
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


def _create_database(database_path):
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE candidate_job_analyses (
            candidate_id TEXT, job_id TEXT, status TEXT,
            opportunity_state TEXT, applied_at TEXT, analysis_json TEXT,
            PRIMARY KEY (candidate_id, job_id)
        );
        CREATE TABLE candidate_application_outcomes (
            candidate_id TEXT, job_id TEXT, final_status TEXT NOT NULL DEFAULT '',
            interview_stage TEXT NOT NULL DEFAULT '', rejection_reason TEXT NOT NULL DEFAULT '',
            recruiter_feedback TEXT NOT NULL DEFAULT '', candidate_notes TEXT NOT NULL DEFAULT '',
            offer_salary TEXT NOT NULL DEFAULT '', offer_currency TEXT NOT NULL DEFAULT '',
            lessons_learned TEXT NOT NULL DEFAULT '', outcome_date TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, job_id)
        );
        INSERT INTO candidate_job_analyses VALUES
            ('candidate-a', 'job-1', 'applied', 'applied', 'earlier', '{"fit": 90}'),
            ('candidate-b', 'job-1', 'applied', 'applied', 'earlier', '{"fit": 40}');
        """
    )
    connection.commit()
    connection.close()


def test_repository_is_candidate_scoped_and_preserves_analysis(
    monkeypatch, tmp_path: Path
):
    database_path = tmp_path / "outcomes.db"
    _create_database(database_path)
    _install_database(monkeypatch, database_path)
    service = _service(ApplicationOutcomeRepository())

    result = service.mark_interview("candidate-a", "job-1")

    connection = sqlite3.connect(database_path)
    analyses = connection.execute(
        "SELECT candidate_id, analysis_json FROM candidate_job_analyses ORDER BY candidate_id"
    ).fetchall()
    outcomes = connection.execute(
        "SELECT candidate_id, job_id, interview_stage FROM candidate_application_outcomes"
    ).fetchall()
    connection.close()
    assert result.status == "updated"
    assert analyses == [
        ("candidate-a", '{"fit": 90}'),
        ("candidate-b", '{"fit": 40}'),
    ]
    assert outcomes == [("candidate-a", "job-1", "interview")]


def test_repository_rejects_outcome_without_candidate_job_relationship(
    monkeypatch, tmp_path: Path
):
    database_path = tmp_path / "outcomes.db"
    _create_database(database_path)
    _install_database(monkeypatch, database_path)

    with pytest.raises(ValueError, match="relationship was not found"):
        ApplicationOutcomeRepository().save(
            ApplicationOutcome(
                candidate_id="candidate-a",
                job_id="missing",
                interview_stage="interview",
                created_at="now",
                updated_at="now",
            )
        )


class CandidateRepository:
    def get(self, candidate_id):
        if candidate_id != "candidate-a":
            return None
        return Candidate(
            id="candidate-a", name="Candidate", current_role="Operator",
            current_level="Specialist", professional_summary="",
        )


class EmptyUpdates:
    def list_for_candidate(self, candidate_id):
        return []


def test_career_evidence_service_reads_persisted_candidate_outcome(
    monkeypatch, tmp_path: Path
):
    database_path = tmp_path / "outcomes.db"
    _create_database(database_path)
    _install_database(monkeypatch, database_path)
    repository = ApplicationOutcomeRepository()
    outcome_service = _service(repository)
    outcome_service.mark_interview("candidate-a", "job-1")
    outcome_service.mark_final_interview("candidate-a", "job-1")
    outcome_service.mark_offer("candidate-a", "job-1")

    evidence_service = CareerEvidenceService(
        candidate_repository=CandidateRepository(),
        career_update_repository=EmptyUpdates(),
        market_signal_loader=lambda candidate_id: [],
        outcome_loader=lambda candidate_id: [
            asdict(repository.get(candidate_id, "job-1"))
        ],
    )
    result = evidence_service.build("candidate-a")

    outcomes = [
        item for item in result["records"]
        if item.evidence_type == "application_outcome"
    ]
    assert len(outcomes) == 1
    assert outcomes[0].statement == "offer"
    assert outcomes[0].metadata["interview_stage"] == "final_interview"


@pytest.mark.parametrize(
    ("final_status", "stage", "actor", "employer_rejection"),
    [
        ("", "interview", "employer", False),
        ("", "final_interview", "employer", False),
        ("offer", "final_interview", "employer", False),
        ("rejected", "", "employer", True),
        ("withdrawn", "interview", "candidate", False),
        ("declined", "final_interview", "candidate", False),
        ("accepted", "final_interview", "candidate", False),
    ],
)
def test_career_evidence_preserves_outcome_meaning(
    final_status, stage, actor, employer_rejection
):
    outcome = ApplicationOutcome(
        candidate_id="candidate-a", job_id="job-1",
        final_status=final_status, interview_stage=stage,
        outcome_date="2026-09-12",
    )
    service = CareerEvidenceService(
        candidate_repository=CandidateRepository(),
        career_update_repository=EmptyUpdates(),
        market_signal_loader=lambda candidate_id: [],
        outcome_loader=lambda candidate_id: [asdict(outcome)],
    )

    result = service.build("candidate-a")
    records = [
        item for item in result["records"]
        if item.evidence_type == "application_outcome"
    ]

    assert len(records) == 1
    assert records[0].statement == (final_status or stage)
    assert records[0].metadata["outcome_actor"] == actor
    assert records[0].metadata["is_employer_rejection"] is employer_rejection
    assert result["counts"]["outcomes"] == 1


def test_outcome_code_has_no_ai_api_path():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "models/application_outcome.py",
            "services/application_outcome_repository.py",
            "services/application_outcome_service.py",
        )
    ).lower()

    assert "openai" not in source
    assert "llm" not in source
    assert "generate(" not in source
