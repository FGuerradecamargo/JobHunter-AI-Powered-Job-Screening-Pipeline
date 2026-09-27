from __future__ import annotations

from services.interview_context_service import InterviewContextService
from services.interview_feedback_repository import InterviewFeedbackRepository
from services.interview_preparation_builder import build_interview_preparation


class InterviewPreparationService:
    def build_brief(self, candidate_id: str, job_id: str, interview_id: str):
        """Reload the official relationship and verified earlier rounds; never research here."""
        from services.interview_round_repository import InterviewRoundRepository
        from services.application_outcome_repository import ApplicationOutcomeRepository
        from services.application_context_service import ApplicationContextService
        from services.application_contract_service import ApplicationContractService
        from services.hiring_case_compatibility import read_hiring_case
        from services.interview_prep_contract_builder import build_interview_prep_contract
        from services.interview_context_builder import build_interview_context
        from services.interview_brief_builder import build_interview_brief
        from services.company_repository import CompanyRepository
        from services.company_profile_repository import CompanyProfileRepository
        from models.interview_context import InterviewDetails

        application = ApplicationOutcomeRepository().get_application(candidate_id, job_id)
        if application is None or application["status"] not in {"applied", "in_process", "offer"}:
            raise ValueError("An applied relationship is required.")
        repository = InterviewRoundRepository()
        rounds = repository.list(candidate_id, job_id)
        selected = next((item for item in rounds if item.interview_id == interview_id), None)
        if selected is None:
            raise PermissionError("Interview round was not found in this relationship.")
        application_contract, source = ApplicationContractService().build_with_source(candidate_id, job_id)
        context = ApplicationContextService().build_from_contract(application_contract, source)
        case = read_hiring_case(source.analysis, candidate_id=candidate_id, job_id=job_id)
        if case is None:
            raise ValueError("An official HiringCase is required.")
        contract = build_interview_prep_contract(context=context, interview_stage="interview", eligible=True)
        interview_context = build_interview_context(contract=contract, details=InterviewDetails(
            candidate_id=candidate_id, job_id=job_id, scheduled_at=selected.scheduled_at,
            interview_type=selected.interview_type, interviewer=", ".join(selected.interviewer_names),
        ))
        preparation = build_interview_preparation(interview_context, hiring_case=case)
        previous = tuple(item for item in rounds if item.sequence < selected.sequence)
        feedback = tuple(item for prior in previous
                         if (item := repository.feedback_for(prior.interview_id, candidate_id, job_id)) is not None)
        # Exact registry identity only. No fuzzy company resolution or private research.
        company = CompanyRepository().find_company(context.company) if context.company else None
        profile = CompanyProfileRepository().current(company.id) if company else None
        return build_interview_brief(preparation=preparation, interview_round=selected,
            company_profile=profile, expected_company_id=company.id if company else "",
            previous_rounds=previous, previous_feedback=feedback)

    def __init__(self, *, context_service=None, feedback_repository=None) -> None:
        injected_context = context_service is not None
        self.context_service = context_service or InterviewContextService()
        self.feedback_repository = feedback_repository
        if feedback_repository is None and not injected_context:
            self.feedback_repository = InterviewFeedbackRepository()

    def build(self, candidate_id: str, job_id: str):
        candidate_id = str(candidate_id or "").strip()
        job_id = str(job_id or "").strip()
        if not candidate_id or not job_id:
            raise ValueError("candidate_id and job_id must be non-empty.")
        context = self.context_service.build(candidate_id, job_id)
        if context.candidate_id != candidate_id:
            raise PermissionError("Interview Context belongs to another candidate.")
        if context.job_id != job_id:
            raise PermissionError("Interview Context belongs to another job.")
        feedback = (
            self.feedback_repository.get(candidate_id, job_id)
            if self.feedback_repository is not None
            else None
        )
        if feedback is not None and (
            feedback.candidate_id != candidate_id or feedback.job_id != job_id
        ):
            raise PermissionError("Interview feedback belongs to another scope.")
        return build_interview_preparation(context, feedback=feedback)
