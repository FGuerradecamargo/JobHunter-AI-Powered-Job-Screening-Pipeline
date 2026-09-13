from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from models.application_outcome import (
    ApplicationOutcome,
    ApplicationOutcomeResult,
)
from services.application_outcome_repository import ApplicationOutcomeRepository


INTERVIEW = "interview"
FINAL_INTERVIEW = "final_interview"
OFFER = "offer"
TERMINAL_STATUSES = {"rejected", "accepted", "declined", "withdrawn"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApplicationOutcomeService:
    def __init__(
        self,
        repository: ApplicationOutcomeRepository | None = None,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.repository = repository or ApplicationOutcomeRepository()
        self.clock = clock

    def mark_interview(self, candidate_id: str, job_id: str, **details):
        return self._transition(candidate_id, job_id, INTERVIEW, **details)

    def mark_final_interview(self, candidate_id: str, job_id: str, **details):
        return self._transition(candidate_id, job_id, FINAL_INTERVIEW, **details)

    def mark_offer(
        self,
        candidate_id: str,
        job_id: str,
        *,
        offer_salary: str | None = None,
        offer_currency: str | None = None,
        **details,
    ):
        return self._transition(
            candidate_id,
            job_id,
            OFFER,
            offer_salary=offer_salary,
            offer_currency=offer_currency,
            **details,
        )

    def mark_rejected(self, candidate_id: str, job_id: str, **details):
        return self._transition(candidate_id, job_id, "rejected", **details)

    def mark_accepted(self, candidate_id: str, job_id: str, **details):
        return self._transition(candidate_id, job_id, "accepted", **details)

    def mark_declined(self, candidate_id: str, job_id: str, **details):
        return self._transition(candidate_id, job_id, "declined", **details)

    def mark_withdrawn(self, candidate_id: str, job_id: str, **details):
        return self._transition(candidate_id, job_id, "withdrawn", **details)

    def _transition(
        self,
        candidate_id: str,
        job_id: str,
        target: str,
        *,
        rejection_reason: str | None = None,
        recruiter_feedback: str | None = None,
        candidate_notes: str | None = None,
        offer_salary: str | None = None,
        offer_currency: str | None = None,
        lessons_learned: str | None = None,
    ) -> ApplicationOutcomeResult:
        application = self.repository.get_application(candidate_id, job_id)
        if application is None:
            return self._failed(candidate_id, job_id, "candidate_job_not_found")
        if application["status"] not in {
            "applied", "in_process", "rejected_before_interview",
            "rejected_after_interview", "offer",
        }:
            return self._failed(candidate_id, job_id, "application_not_applied")

        current = self.repository.get(candidate_id, job_id)
        current_state = self.current_state(current, application["status"])
        if not self._allowed(current_state, target):
            return self._failed(candidate_id, job_id, "invalid_transition", current)

        now = self.clock()
        desired = self._build_outcome(
            current,
            candidate_id,
            job_id,
            target,
            now,
            rejection_reason=rejection_reason,
            recruiter_feedback=recruiter_feedback,
            candidate_notes=candidate_notes,
            offer_salary=offer_salary,
            offer_currency=offer_currency,
            lessons_learned=lessons_learned,
        )
        if current is not None and self._same_content(current, desired):
            return self._result("already_current", current)

        return self._result("updated", self.repository.save(desired))

    @staticmethod
    def current_state(
        outcome: ApplicationOutcome | None,
        application_status: str = "applied",
    ) -> str:
        if outcome is None:
            return {
                "in_process": INTERVIEW,
                "rejected_before_interview": "rejected",
                "rejected_after_interview": "rejected",
                "offer": OFFER,
            }.get(application_status, "applied")
        if outcome.final_status:
            return outcome.final_status
        return outcome.interview_stage or "applied"

    @staticmethod
    def _allowed(current: str, target: str) -> bool:
        if current == target:
            return True
        return target in {
            "applied": {INTERVIEW, "rejected", "withdrawn"},
            INTERVIEW: {FINAL_INTERVIEW, "rejected", "withdrawn"},
            FINAL_INTERVIEW: {OFFER, "rejected", "withdrawn"},
            OFFER: {"accepted", "declined", "withdrawn"},
        }.get(current, set())

    @staticmethod
    def _build_outcome(
        current: ApplicationOutcome | None,
        candidate_id: str,
        job_id: str,
        target: str,
        now: str,
        **details,
    ) -> ApplicationOutcome:
        base = current or ApplicationOutcome(
            candidate_id=candidate_id,
            job_id=job_id,
            created_at=now,
        )
        interview_stage = base.interview_stage
        final_status = base.final_status
        if target in {INTERVIEW, FINAL_INTERVIEW}:
            interview_stage = target
            final_status = ""
        else:
            final_status = target

        supplied_details = {
            key: value
            for key, value in details.items()
            if value is not None
        }
        return replace(
            base,
            interview_stage=interview_stage,
            final_status=final_status,
            outcome_date=now,
            updated_at=now,
            **supplied_details,
        )

    @staticmethod
    def _same_content(first: ApplicationOutcome, second: ApplicationOutcome) -> bool:
        ignored = {"outcome_date", "created_at", "updated_at"}
        return all(
            getattr(first, field) == getattr(second, field)
            for field in first.__dataclass_fields__
            if field not in ignored
        )

    @staticmethod
    def _result(status: str, outcome: ApplicationOutcome) -> ApplicationOutcomeResult:
        return ApplicationOutcomeResult(
            status=status,
            candidate_id=outcome.candidate_id,
            job_id=outcome.job_id,
            interview_stage=outcome.interview_stage,
            final_status=outcome.final_status,
            outcome_date=outcome.outcome_date,
            created_at=outcome.created_at,
            updated_at=outcome.updated_at,
        )

    @staticmethod
    def _failed(
        candidate_id: str,
        job_id: str,
        error_code: str,
        outcome: ApplicationOutcome | None = None,
    ) -> ApplicationOutcomeResult:
        result = ApplicationOutcomeResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code=error_code,
        )
        return result if outcome is None else replace(
            result,
            interview_stage=outcome.interview_stage,
            final_status=outcome.final_status,
            outcome_date=outcome.outcome_date,
            created_at=outcome.created_at,
            updated_at=outcome.updated_at,
        )
