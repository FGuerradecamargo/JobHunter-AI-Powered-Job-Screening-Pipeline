from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from models.application_lifecycle import ApplicationLifecycleResult
from services.application_lifecycle_repository import ApplicationLifecycleRepository


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApplicationLifecycleService:
    def __init__(
        self,
        repository: ApplicationLifecycleRepository | None = None,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.repository = repository or ApplicationLifecycleRepository()
        self.clock = clock

    def mark_applied(
        self,
        candidate_id: str,
        job_id: str,
    ) -> ApplicationLifecycleResult:
        current = self.repository.get(candidate_id, job_id)
        if current is None:
            return self._missing(candidate_id, job_id)

        if current["status"] == "applied":
            return self._result("already_applied", current)

        if current["status"] not in {"in_review", "user_rejected"}:
            return self._invalid_transition(candidate_id, job_id, current)

        updated = self.repository.mark_applied(
            candidate_id,
            job_id,
            self.clock(),
        )
        if updated is None:
            return self._missing(candidate_id, job_id)

        return self._result("applied", updated)

    def mark_user_rejected(
        self,
        candidate_id: str,
        job_id: str,
    ) -> ApplicationLifecycleResult:
        current = self.repository.get(candidate_id, job_id)
        if current is None:
            return self._missing(candidate_id, job_id)

        if current["status"] == "user_rejected":
            return self._result("already_user_rejected", current)

        if current["status"] != "in_review":
            return self._invalid_transition(candidate_id, job_id, current)

        updated = self.repository.mark_user_rejected(
            candidate_id,
            job_id,
            self.clock(),
        )
        if updated is None:
            return self._missing(candidate_id, job_id)

        return self._result("user_rejected", updated)

    @staticmethod
    def _missing(candidate_id: str, job_id: str) -> ApplicationLifecycleResult:
        return ApplicationLifecycleResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code="candidate_job_not_found",
        )

    @staticmethod
    def _invalid_transition(
        candidate_id: str,
        job_id: str,
        row: dict,
    ) -> ApplicationLifecycleResult:
        return ApplicationLifecycleResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            opportunity_state=str(row["opportunity_state"]),
            applied_at=row.get("applied_at"),
            error_code="invalid_transition",
        )

    @staticmethod
    def _result(status: str, row: dict) -> ApplicationLifecycleResult:
        return ApplicationLifecycleResult(
            status=status,
            candidate_id=str(row["candidate_id"]),
            job_id=str(row["job_id"]),
            opportunity_state=str(row["opportunity_state"]),
            applied_at=row.get("applied_at"),
        )
