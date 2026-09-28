from __future__ import annotations

from services.application_contract_repository import (
    ApplicationContractSourceRepository,
)
from services.hiring_case_compatibility import read_hiring_case
from services.interview_context_service import InterviewContextService
from services.interview_feedback_repository import InterviewFeedbackRepository
from services.interview_preparation_builder import build_interview_preparation


class InterviewPreparationService:
    """
    One preparation pipeline for both the general interview view
    and round-specific briefs.

    Modern applications may use the official HiringCase for
    requirement-to-evidence links. Legacy active interviews rely
    on the compatibility contract produced upstream.

    This service never performs company research.
    """

    def __init__(
        self,
        *,
        context_service=None,
        feedback_repository=None,
        hiring_case_loader=None,
    ) -> None:
        injected_context = context_service is not None

        self.context_service = (
            context_service
            or InterviewContextService()
        )

        self.feedback_repository = (
            feedback_repository
        )

        if (
            feedback_repository is None
            and not injected_context
        ):
            self.feedback_repository = (
                InterviewFeedbackRepository()
            )

        # Unit/injected contexts should remain isolated from the
        # database unless a loader is explicitly supplied.
        if hiring_case_loader is not None:
            self.hiring_case_loader = (
                hiring_case_loader
            )
        elif injected_context:
            self.hiring_case_loader = None
        else:
            self.hiring_case_loader = (
                self._load_current_hiring_case
            )

    @staticmethod
    def _load_current_hiring_case(
        candidate_id: str,
        job_id: str,
    ):
        source = (
            ApplicationContractSourceRepository()
            .get_analysis_source(
                candidate_id,
                job_id,
            )
        )

        if source is None:
            return None

        if (
            source.candidate_id != candidate_id
            or source.job_id != job_id
        ):
            raise PermissionError(
                "Interview analysis source belongs to another scope."
            )

        # Returns None for genuine pre-HiringCase analyses.
        return read_hiring_case(
            source.analysis,
            candidate_id=candidate_id,
            job_id=job_id,
        )

    def build(
        self,
        candidate_id: str,
        job_id: str,
    ):
        candidate_id = str(
            candidate_id or ""
        ).strip()

        job_id = str(
            job_id or ""
        ).strip()

        if not candidate_id or not job_id:
            raise ValueError(
                "candidate_id and job_id must be non-empty."
            )

        context = self.context_service.build(
            candidate_id,
            job_id,
        )

        if context.candidate_id != candidate_id:
            raise PermissionError(
                "Interview Context belongs to another candidate."
            )

        if context.job_id != job_id:
            raise PermissionError(
                "Interview Context belongs to another job."
            )

        feedback = (
            self.feedback_repository.get(
                candidate_id,
                job_id,
            )
            if self.feedback_repository is not None
            else None
        )

        if feedback is not None and (
            feedback.candidate_id != candidate_id
            or feedback.job_id != job_id
        ):
            raise PermissionError(
                "Interview feedback belongs to another scope."
            )

        hiring_case = (
            self.hiring_case_loader(
                candidate_id,
                job_id,
            )
            if self.hiring_case_loader is not None
            else None
        )

        return build_interview_preparation(
            context,
            feedback=feedback,
            hiring_case=hiring_case,
        )

    def build_brief(
        self,
        candidate_id: str,
        job_id: str,
        interview_id: str,
    ):
        """
        Build a round-specific brief from the same official
        preparation used by the general interview view.

        Company research is never performed here. Only an already
        persisted CompanyProfile may be read.
        """
        from services.application_outcome_repository import (
            ApplicationOutcomeRepository,
        )
        from services.company_profile_repository import (
            CompanyProfileRepository,
        )
        from services.company_repository import (
            CompanyRepository,
        )
        from services.interview_brief_builder import (
            build_interview_brief,
        )
        from services.interview_round_repository import (
            InterviewRoundRepository,
        )

        application = (
            ApplicationOutcomeRepository()
            .get_application(
                candidate_id,
                job_id,
            )
        )

        if (
            application is None
            or application["status"]
            not in {
                "applied",
                "in_process",
                "offer",
            }
        ):
            raise ValueError(
                "An applied relationship is required."
            )

        repository = InterviewRoundRepository()

        rounds = repository.list(
            candidate_id,
            job_id,
        )

        selected = next(
            (
                item
                for item in rounds
                if item.interview_id
                == interview_id
            ),
            None,
        )

        if selected is None:
            raise PermissionError(
                "Interview round was not found in this relationship."
            )

        # Critical consolidation:
        # overview and round brief now share the same preparation path.
        preparation = self.build(
            candidate_id,
            job_id,
        )

        previous = tuple(
            item
            for item in rounds
            if item.sequence
            < selected.sequence
        )

        feedback = tuple(
            item
            for prior in previous
            if (
                item := repository.feedback_for(
                    prior.interview_id,
                    candidate_id,
                    job_id,
                )
            )
            is not None
        )

        analysis_source = (
            ApplicationContractSourceRepository()
            .get_analysis_source(
                candidate_id,
                job_id,
            )
        )

        company_name = ""

        if analysis_source is not None:
            if (
                analysis_source.candidate_id
                != candidate_id
                or analysis_source.job_id
                != job_id
            ):
                raise PermissionError(
                    "Application analysis belongs to another scope."
                )

            company_name = str(
                analysis_source.job.get(
                    "company"
                )
                or ""
            ).strip()

        # Exact registry identity only.
        # No fuzzy company resolution and no research on this read path.
        company = (
            CompanyRepository()
            .find_company(
                company_name
            )
            if company_name
            else None
        )

        profile = (
            CompanyProfileRepository()
            .current(
                company.id
            )
            if company
            else None
        )

        return build_interview_brief(
            preparation=preparation,
            interview_round=selected,
            company_profile=profile,
            expected_company_id=(
                company.id
                if company
                else ""
            ),
            previous_rounds=previous,
            previous_feedback=feedback,
        )
