from models.application_contract import ApplicationContract
from services.application_contract_builder import build_application_contract
from services.application_contract_repository import ApplicationContractSourceRepository
from services.candidate_repository import CandidateRepository
from services.career_update_repository import CareerUpdateRepository


class ApplicationAnalysisNotFoundError(ValueError):
    pass


class ApplicationContractService:
    def __init__(
        self,
        *,
        candidate_repository=None,
        career_update_repository=None,
        source_repository=None,
    ) -> None:
        self.candidate_repository = candidate_repository or CandidateRepository()
        self.career_update_repository = (
            career_update_repository or CareerUpdateRepository()
        )
        self.source_repository = (
            source_repository or ApplicationContractSourceRepository()
        )

    def build(self, candidate_id: str, job_id: str) -> ApplicationContract:
        contract, _ = self.build_with_source(candidate_id, job_id)
        return contract

    def build_with_source(
        self,
        candidate_id: str,
        job_id: str,
    ):
        normalized_candidate_id = str(candidate_id or "").strip()
        normalized_job_id = str(job_id or "").strip()
        if not normalized_candidate_id:
            raise ValueError("candidate_id must be non-empty.")
        if not normalized_job_id:
            raise ValueError("job_id must be non-empty.")

        candidate = self.candidate_repository.get(normalized_candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate was not found: {normalized_candidate_id}")
        if candidate.id != normalized_candidate_id:
            raise PermissionError("Candidate repository returned another candidate.")

        updates = self.career_update_repository.list_for_candidate(
            normalized_candidate_id
        )
        source = self.source_repository.get_analysis_source(
            normalized_candidate_id,
            normalized_job_id,
        )
        if source is None:
            raise ApplicationAnalysisNotFoundError(
                "Analyzed candidate-job opportunity was not found."
            )

        contract = build_application_contract(
            candidate=candidate,
            career_updates=updates,
            analysis_source=source,
        )
        return contract, source
