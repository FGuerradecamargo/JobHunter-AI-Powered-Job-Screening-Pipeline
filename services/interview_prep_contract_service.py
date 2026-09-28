from __future__ import annotations

from services.application_context_service import ApplicationContextService
from services.application_outcome_repository import ApplicationOutcomeRepository
from services.interview_prep_contract_builder import (
    INTERVIEW_PREP_ELIGIBLE_STAGES,
    build_interview_prep_contract,
)


class InterviewPrepSourceNotFoundError(ValueError):
    pass


class InterviewPrepContractService:
    def __init__(
        self,
        *,
        context_service=None,
        outcome_repository=None,
        legacy_contract_builder=None,
    ) -> None:
        self.context_service = context_service or ApplicationContextService()
        self.outcome_repository = outcome_repository or ApplicationOutcomeRepository()

        if legacy_contract_builder is None:
            from services.legacy_interview_prep_compatibility import (
                build_legacy_active_interview_prep_contract,
            )

            legacy_contract_builder = (
                build_legacy_active_interview_prep_contract
            )

        self.legacy_contract_builder = legacy_contract_builder

    def build(self, candidate_id: str, job_id: str):
        candidate_id = str(candidate_id or "").strip()
        job_id = str(job_id or "").strip()
        if not candidate_id or not job_id:
            raise ValueError("candidate_id and job_id must be non-empty.")

        application = self.outcome_repository.get_application(candidate_id, job_id)
        if application is None:
            raise InterviewPrepSourceNotFoundError(
                "Candidate-job application relationship was not found."
            )
        if (
            str(application.get("candidate_id")) != candidate_id
            or str(application.get("job_id")) != job_id
        ):
            raise PermissionError("Application relationship belongs to another scope.")

        outcome = self.outcome_repository.get(candidate_id, job_id)
        if outcome is not None and (
            outcome.candidate_id != candidate_id or outcome.job_id != job_id
        ):
            raise PermissionError("Application outcome belongs to another scope.")

        final_status = str(outcome.final_status if outcome else "").strip()
        interview_stage = str(outcome.interview_stage if outcome else "").strip()
        if outcome is None and application.get("status") == "in_process":
            interview_stage = "interview"
        eligible = bool(
            not final_status
            and interview_stage.casefold() in INTERVIEW_PREP_ELIGIBLE_STAGES
        )

        try:
            context = self.context_service.build(
                candidate_id,
                job_id,
            )

        except ValueError as exc:
            # Compatibility is intentionally narrower than the normal
            # Application Context boundary. It is only available when:
            #   1) there is already an active interview,
            #   2) the failure is the legacy not-eligible sentinel, and
            #   3) the compatibility builder confirms this is truly a
            #      pre-HiringCase analysis.
            if (
                not eligible
                or str(exc)
                != "Application contract is not eligible."
            ):
                raise

            try:
                return self.legacy_contract_builder(
                    candidate_id,
                    job_id,
                    interview_stage=interview_stage,
                    application_final_status=final_status,
                )

            except (
                ValueError,
                PermissionError,
            ):
                # Never let compatibility weaken the existing fail-closed
                # behavior when the source cannot be proven legacy-safe.
                raise exc from None

        if (
            context.candidate_id != candidate_id
            or context.job_id != job_id
        ):
            raise PermissionError(
                "Application Context belongs to another scope."
            )

        return build_interview_prep_contract(
            context=context,
            interview_stage=interview_stage,
            application_final_status=final_status,
            eligible=eligible,
        )
