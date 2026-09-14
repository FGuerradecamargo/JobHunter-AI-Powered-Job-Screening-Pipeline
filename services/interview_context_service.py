from __future__ import annotations

from services.interview_context_builder import build_interview_context
from services.interview_details_repository import InterviewDetailsRepository
from services.interview_prep_contract_service import InterviewPrepContractService


class InterviewContextService:
    def __init__(self, *, contract_service=None, details_repository=None) -> None:
        self.contract_service = contract_service or InterviewPrepContractService()
        self.details_repository = details_repository or InterviewDetailsRepository()

    def build(self, candidate_id: str, job_id: str):
        candidate_id = str(candidate_id or "").strip()
        job_id = str(job_id or "").strip()
        if not candidate_id or not job_id:
            raise ValueError("candidate_id and job_id must be non-empty.")

        contract = self.contract_service.build(candidate_id, job_id)
        if contract.candidate_id != candidate_id or contract.job_id != job_id:
            raise PermissionError("Interview Prep Contract belongs to another scope.")
        if not contract.eligible:
            raise ValueError("Application is not in an active interview stage.")

        details = self.details_repository.get(candidate_id, job_id)
        if details is not None and (
            details.candidate_id != candidate_id or details.job_id != job_id
        ):
            raise PermissionError("Interview details belong to another scope.")
        return build_interview_context(contract=contract, details=details)
