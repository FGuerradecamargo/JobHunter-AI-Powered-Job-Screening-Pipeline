"""Candidate-only public boundary for authoritative profile snapshots."""
from models.profile_interpretation import CandidateProfileSnapshot
from services.candidate_profile_generation_service import CandidateProfileGenerationService
from services.profile_readiness_service import ProfileReadiness, ProfileReadinessService
from services.profile_snapshot_repository import ProfileSnapshotRepository


class CandidateProfileService:
    def __init__(
        self,
        *,
        snapshot_repository: ProfileSnapshotRepository,
        readiness_service: ProfileReadinessService,
        generation_service: CandidateProfileGenerationService,
    ) -> None:
        self._snapshots = snapshot_repository
        self._readiness = readiness_service
        self._generation = generation_service

    def current(self, candidate_id: str) -> CandidateProfileSnapshot | None:
        return self._snapshots.current_candidate(candidate_id)

    def check_readiness(self, candidate_id: str) -> ProfileReadiness:
        return self._readiness.check(candidate_id)

    def generate_snapshot(self, candidate_id: str) -> CandidateProfileSnapshot:
        return self._generation.generate_snapshot(candidate_id)
