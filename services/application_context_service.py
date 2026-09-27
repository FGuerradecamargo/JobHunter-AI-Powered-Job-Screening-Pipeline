from models.application_context import ApplicationContext
from services.application_context_builder import build_application_context
from services.application_contract_builder import build_application_contract
from services.application_contract_repository import ApplicationContractSourceRepository
from services.candidate_repository import CandidateRepository
from services.career_update_repository import CareerUpdateRepository
from services.application_contract_service import ApplicationContractService


class ApplicationContextService:
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

    def build(self, candidate_id: str, job_id: str) -> ApplicationContext:
        normalized_candidate_id = str(candidate_id or "").strip()
        normalized_job_id = str(job_id or "").strip()
        if not normalized_candidate_id:
            raise ValueError("candidate_id must be non-empty.")
        if not normalized_job_id:
            raise ValueError("job_id must be non-empty.")

        contract, source = ApplicationContractService(
            candidate_repository=self.candidate_repository, career_update_repository=self.career_update_repository,
            source_repository=self.source_repository,
        ).build_with_source(normalized_candidate_id, normalized_job_id)
        return build_application_context(
            contract=contract,
            analysis_source=source,
        )

    def build_from_contract(
        self,
        contract,
        analysis_source,
    ) -> ApplicationContext:
        return build_application_context(
            contract=contract,
            analysis_source=analysis_source,
        )
