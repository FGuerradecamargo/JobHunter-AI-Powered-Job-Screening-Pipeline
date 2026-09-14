from __future__ import annotations

from services.interview_context_service import InterviewContextService
from services.interview_preparation_builder import build_interview_preparation


class InterviewPreparationService:
    def __init__(self, *, context_service=None) -> None:
        self.context_service = context_service or InterviewContextService()

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
        return build_interview_preparation(context)
