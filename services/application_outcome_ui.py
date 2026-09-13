from __future__ import annotations

from dataclasses import dataclass

from models.application_outcome import ApplicationOutcome, ApplicationOutcomeResult
from services.application_outcome_repository import ApplicationOutcomeRepository
from services.application_outcome_service import ApplicationOutcomeService


@dataclass(frozen=True)
class OutcomeAction:
    value: str
    label: str


@dataclass(frozen=True)
class ApplicationOutcomeView:
    state: str
    status_label: str
    actions: tuple[OutcomeAction, ...]
    outcome: ApplicationOutcome | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in {"accepted", "declined", "rejected", "withdrawn"}


STATUS_LABELS = {
    "applied": "Applied",
    "interview": "Interview",
    "final_interview": "Final interview",
    "offer": "Offer",
    "accepted": "Accepted",
    "declined": "Declined",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

ACTION_LABELS = {
    "interview": "Interview",
    "final_interview": "Final interview",
    "offer": "Offer",
    "accepted": "Accepted",
    "declined": "Declined",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

VALID_ACTIONS = {
    "applied": ("interview", "rejected", "withdrawn"),
    "interview": ("final_interview", "rejected", "withdrawn"),
    "final_interview": ("offer", "rejected", "withdrawn"),
    "offer": ("accepted", "declined", "withdrawn"),
}

ELIGIBLE_LIFECYCLE_STATUSES = {
    "applied",
    "in_process",
    "rejected_before_interview",
    "rejected_after_interview",
    "offer",
}


def load_application_outcome_view(
    *,
    candidate_id: str,
    job_id: str,
    lifecycle_status: str,
    repository: ApplicationOutcomeRepository,
) -> ApplicationOutcomeView | None:
    if lifecycle_status not in ELIGIBLE_LIFECYCLE_STATUSES:
        return None

    outcome = repository.get(candidate_id, job_id)
    state = ApplicationOutcomeService.current_state(outcome, lifecycle_status)
    actions = tuple(
        OutcomeAction(value=value, label=ACTION_LABELS[value])
        for value in VALID_ACTIONS.get(state, ())
    )
    return ApplicationOutcomeView(
        state=state,
        status_label=STATUS_LABELS.get(state, "Application updated"),
        actions=actions,
        outcome=outcome,
    )


def dispatch_application_outcome_action(
    *,
    confirmed: bool,
    action: str,
    candidate_id: str,
    job_id: str,
    lifecycle_status: str,
    service: ApplicationOutcomeService,
    rejection_reason: str = "",
    recruiter_feedback: str = "",
    candidate_notes: str = "",
    offer_salary: str = "",
    offer_currency: str = "",
) -> ApplicationOutcomeResult | None:
    if not confirmed:
        return None

    view = load_application_outcome_view(
        candidate_id=candidate_id,
        job_id=job_id,
        lifecycle_status=lifecycle_status,
        repository=service.repository,
    )
    if view is None or action not in {item.value for item in view.actions}:
        return ApplicationOutcomeResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code="invalid_transition",
        )

    details = {
        "candidate_notes": candidate_notes,
    }
    if action == "rejected":
        details.update(
            rejection_reason=rejection_reason,
            recruiter_feedback=recruiter_feedback,
        )
    if action == "offer":
        details.update(
            offer_salary=offer_salary,
            offer_currency=offer_currency,
        )

    transition = getattr(service, f"mark_{action}")
    return transition(candidate_id, job_id, **details)


def outcome_result_message(result: ApplicationOutcomeResult) -> str:
    if result.succeeded:
        return "Application status updated."
    if result.error_code == "application_not_applied":
        return "Mark this opportunity as applied before recording progress."
    return "The application status could not be updated. Refresh and try again."
