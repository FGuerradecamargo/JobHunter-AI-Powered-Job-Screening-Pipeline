from pathlib import Path

import pytest

from models.application_outcome import ApplicationOutcome, ApplicationOutcomeResult
from services.application_outcome_ui import (
    dispatch_application_outcome_action,
    load_application_outcome_view,
    outcome_result_message,
)


class FakeRepository:
    def __init__(self, outcome=None):
        self.outcome = outcome
        self.reads = []

    def get(self, candidate_id, job_id):
        self.reads.append((candidate_id, job_id))
        if (candidate_id, job_id) != ("candidate-a", "job-1"):
            return None
        return self.outcome


class FakeService:
    def __init__(self, outcome=None, result=None):
        self.repository = FakeRepository(outcome)
        self.calls = []
        self.result = result

    def _call(self, action, candidate_id, job_id, **details):
        self.calls.append((action, candidate_id, job_id, details))
        if (candidate_id, job_id) != ("candidate-a", "job-1"):
            return ApplicationOutcomeResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                error_code="candidate_job_not_found",
            )
        return self.result or ApplicationOutcomeResult(
            status="updated",
            candidate_id=candidate_id,
            job_id=job_id,
            interview_stage=(
                action if action in {"interview", "final_interview"} else ""
            ),
            final_status=(
                "" if action in {"interview", "final_interview"} else action
            ),
        )

    def mark_interview(self, candidate_id, job_id, **details):
        return self._call("interview", candidate_id, job_id, **details)

    def mark_final_interview(self, candidate_id, job_id, **details):
        return self._call("final_interview", candidate_id, job_id, **details)

    def mark_offer(self, candidate_id, job_id, **details):
        return self._call("offer", candidate_id, job_id, **details)

    def mark_rejected(self, candidate_id, job_id, **details):
        return self._call("rejected", candidate_id, job_id, **details)

    def mark_accepted(self, candidate_id, job_id, **details):
        return self._call("accepted", candidate_id, job_id, **details)

    def mark_declined(self, candidate_id, job_id, **details):
        return self._call("declined", candidate_id, job_id, **details)

    def mark_withdrawn(self, candidate_id, job_id, **details):
        return self._call("withdrawn", candidate_id, job_id, **details)


def _outcome(*, stage="", final_status=""):
    return ApplicationOutcome(
        candidate_id="candidate-a",
        job_id="job-1",
        interview_stage=stage,
        final_status=final_status,
    )


@pytest.mark.parametrize(
    ("outcome", "status", "label", "actions"),
    [
        (None, "applied", "Applied", ["interview", "rejected", "withdrawn"]),
        (_outcome(stage="interview"), "applied", "Interview",
         ["final_interview", "rejected", "withdrawn"]),
        (_outcome(stage="final_interview"), "applied", "Final interview",
         ["offer", "rejected", "withdrawn"]),
        (_outcome(stage="final_interview", final_status="offer"), "applied",
         "Offer", ["accepted", "declined", "withdrawn"]),
    ],
)
def test_current_state_exposes_only_valid_actions(outcome, status, label, actions):
    view = load_application_outcome_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status=status,
        repository=FakeRepository(outcome),
    )

    assert view is not None
    assert view.status_label == label
    assert [item.value for item in view.actions] == actions


@pytest.mark.parametrize("terminal", ["accepted", "declined", "rejected", "withdrawn"])
def test_terminal_states_show_status_without_actions(terminal):
    view = load_application_outcome_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        repository=FakeRepository(_outcome(final_status=terminal)),
    )

    assert view is not None and view.is_terminal
    assert view.actions == ()
    assert view.status_label == terminal.capitalize()


@pytest.mark.parametrize("status", ["in_review", "user_rejected", "system_rejected"])
def test_before_applied_has_no_outcome_controls_or_read(status):
    repository = FakeRepository()

    view = load_application_outcome_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status=status,
        repository=repository,
    )

    assert view is None
    assert repository.reads == []


@pytest.mark.parametrize(
    "passive_event",
    ["render", "select_change", "rerender", "prepared_cv_present", "download"],
)
def test_no_confirmation_performs_zero_writes(passive_event):
    service = FakeService()

    result = dispatch_application_outcome_action(
        confirmed=False,
        action="interview",
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
    )

    assert passive_event
    assert result is None
    assert service.calls == []
    assert service.repository.reads == []


def test_explicit_confirmation_performs_exactly_one_transition():
    service = FakeService()

    result = dispatch_application_outcome_action(
        confirmed=True,
        action="interview",
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
    )

    assert result is not None and result.succeeded
    assert len(service.calls) == 1
    assert service.calls[0][:3] == ("interview", "candidate-a", "job-1")


def test_repeated_render_after_success_does_not_repeat_transition():
    service = FakeService()
    dispatch_application_outcome_action(
        confirmed=True,
        action="interview",
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
    )

    dispatch_application_outcome_action(
        confirmed=False,
        action="interview",
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
    )

    assert len(service.calls) == 1


def test_read_is_scoped_to_candidate_and_job():
    repository = FakeRepository()

    load_application_outcome_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        repository=repository,
    )

    assert repository.reads == [("candidate-a", "job-1")]


def test_candidate_mismatch_fails_safely_at_service_boundary():
    service = FakeService()

    result = dispatch_application_outcome_action(
        confirmed=True,
        action="interview",
        candidate_id="candidate-b",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
    )

    assert result is not None
    assert result.status == "failed"
    assert len(service.calls) == 1


def test_rejection_optional_fields_are_forwarded():
    service = FakeService()

    dispatch_application_outcome_action(
        confirmed=True,
        action="rejected",
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
        rejection_reason="Role closed",
        recruiter_feedback="Strong profile",
        candidate_notes="Follow up later",
    )

    assert service.calls[0][3] == {
        "candidate_notes": "Follow up later",
        "rejection_reason": "Role closed",
        "recruiter_feedback": "Strong profile",
    }


def test_offer_optional_salary_and_currency_are_forwarded():
    service = FakeService(_outcome(stage="final_interview"))

    dispatch_application_outcome_action(
        confirmed=True,
        action="offer",
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
        offer_salary="75000",
        offer_currency="GBP",
    )

    assert service.calls[0][3]["offer_salary"] == "75000"
    assert service.calls[0][3]["offer_currency"] == "GBP"


@pytest.mark.parametrize("action", ["accepted", "declined", "withdrawn"])
def test_candidate_action_notes_are_forwarded(action):
    outcome = (
        _outcome(final_status="offer")
        if action in {"accepted", "declined"}
        else None
    )
    service = FakeService(outcome)

    dispatch_application_outcome_action(
        confirmed=True,
        action=action,
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
        candidate_notes="Candidate decision",
    )

    assert service.calls[0][3]["candidate_notes"] == "Candidate decision"


def test_invalid_action_never_reaches_service():
    service = FakeService()

    result = dispatch_application_outcome_action(
        confirmed=True,
        action="accepted",
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        service=service,
    )

    assert result is not None and result.error_code == "invalid_transition"
    assert service.calls == []


def test_failure_message_is_safe_and_contains_no_ids():
    result = ApplicationOutcomeResult(
        status="failed",
        candidate_id="secret-candidate",
        job_id="secret-job",
        error_code="candidate_job_not_found",
    )

    message = outcome_result_message(result)

    assert message == "The application status could not be updated. Refresh and try again."
    assert "secret" not in message


def test_dashboard_uses_service_boundary_not_raw_outcome_writes():
    source = Path("app.py").read_text(encoding="utf-8")

    assert "dispatch_application_outcome_action(" in source
    assert "load_application_outcome_view(" in source
    assert "save_candidate_application_outcome" not in source
    assert "update_candidate_job_status" not in source
    assert '"Confirm update"' in source


def test_outcome_ui_has_no_ai_or_prepared_cv_dependency():
    source = Path("services/application_outcome_ui.py").read_text(
        encoding="utf-8"
    ).lower()

    assert "openai" not in source
    assert "llm" not in source
    assert "prepared_cv" not in source
