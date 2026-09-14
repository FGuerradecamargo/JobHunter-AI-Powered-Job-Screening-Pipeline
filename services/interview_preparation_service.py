from __future__ import annotations

from services.interview_context_service import InterviewContextService
from services.interview_feedback_repository import InterviewFeedbackRepository
from services.interview_preparation_builder import build_interview_preparation


class InterviewPreparationService:
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
