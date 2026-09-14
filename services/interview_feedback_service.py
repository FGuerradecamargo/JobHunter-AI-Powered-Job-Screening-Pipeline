from __future__ import annotations

from models.interview_feedback import InterviewFeedback
from services.interview_context_service import InterviewContextService
from services.interview_feedback_repository import InterviewFeedbackRepository


class InterviewFeedbackService:
    def __init__(self, *, context_service=None, repository=None) -> None:
        self.context_service = context_service or InterviewContextService()
        self.repository = repository or InterviewFeedbackRepository()

    def save(
        self,
        candidate_id: str,
        job_id: str,
        *,
        recruiter_feedback: str = "",
        candidate_notes: str = "",
        discussed_topics=None,
        difficult_topics=None,
        next_stage_instructions: str = "",
    ) -> InterviewFeedback:
        candidate_id = str(candidate_id or "").strip()
        job_id = str(job_id or "").strip()
        context = self.context_service.build(candidate_id, job_id)
        if context.candidate_id != candidate_id or context.job_id != job_id:
            raise PermissionError("Interview Context belongs to another scope.")
        feedback = InterviewFeedback(
            candidate_id=candidate_id,
            job_id=job_id,
            interview_stage=context.interview_stage,
            recruiter_feedback=str(recruiter_feedback or "").strip(),
            candidate_notes=str(candidate_notes or "").strip(),
            discussed_topics=list(discussed_topics or []),
            difficult_topics=list(difficult_topics or []),
            next_stage_instructions=str(next_stage_instructions or "").strip(),
        )
        saved = self.repository.save(feedback)
        if saved.candidate_id != candidate_id or saved.job_id != job_id:
            raise PermissionError("Saved interview feedback belongs to another scope.")
        if saved.interview_stage != context.interview_stage:
            raise PermissionError("Saved interview feedback has a stale stage scope.")
        return saved
