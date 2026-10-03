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
        try:
            return self._readiness.check(candidate_id)
        except Exception:
            return ProfileReadiness("unavailable")

    def generate_snapshot(self, candidate_id: str) -> CandidateProfileSnapshot:
        return self._generation.generate_snapshot(candidate_id)

    def refresh_current(self, candidate_id: str) -> CandidateProfileSnapshot | None:
        readiness = self.check_readiness(candidate_id)
        if readiness.status == "missing":
            return self._readiness.backfill_missing(candidate_id, self._generation)
        return readiness.snapshot if readiness.ready else None
