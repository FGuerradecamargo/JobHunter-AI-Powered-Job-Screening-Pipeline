from models.application_contract import ApplicationContract
from services.application_contract_builder import build_application_contract
from services.application_contract_repository import ApplicationContractSourceRepository
from services.candidate_repository import CandidateRepository
from services.career_update_repository import CareerUpdateRepository
from services.application_contract_builder import build_official_application_contract
from services.hiring_case_compatibility import read_hiring_case
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from services.candidate_profile_source import load_confirmed_candidate_profile_input
from services.job_source_repository import JobSourceRepository


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

        if any(update.candidate_id != normalized_candidate_id for update in updates):
            raise PermissionError("Career update belongs to another candidate.")
        if source.candidate_id != normalized_candidate_id or source.job_id != normalized_job_id:
            raise PermissionError("Application source belongs to another relationship.")

        case = read_hiring_case(source.analysis, candidate_id=normalized_candidate_id, job_id=normalized_job_id)
        if case is None:
            return ApplicationContract(normalized_candidate_id, normalized_job_id,
                source.analysis_id, "not_surfaced", False), source
        snapshots = ProfileSnapshotRepository()
        candidate_profile = snapshots.current_candidate(normalized_candidate_id)
        job_profile = snapshots.current_job(normalized_job_id)
        if candidate_profile is None or job_profile is None:
            raise ValueError("Application source profiles are unavailable.")
        hard_facts = JobSourceRepository().load_job_hard_facts(normalized_job_id, candidate_id=normalized_candidate_id)
        if job_profile.job_signature != hard_facts.job_signature:
            raise ValueError("Job source changed; reanalysis is required.")
        source_snapshot, evidence = load_confirmed_candidate_profile_input(
            normalized_candidate_id, CandidateOnboardingRepository(), self.career_update_repository,
        )
        contract = build_official_application_contract(candidate_profile=candidate_profile, job_profile=job_profile,
            hiring_case=case, source_snapshot=source_snapshot, source_evidence=evidence, analysis_source=source)
        return contract, source
