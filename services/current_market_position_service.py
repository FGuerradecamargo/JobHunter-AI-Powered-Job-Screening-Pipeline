from models.current_market_position import CurrentMarketPosition
from services.career_evidence_service import CareerEvidenceService
from services.career_objective_repository import CareerObjectiveRepository
from services.current_market_position_builder import (
    build_current_market_position,
)
from services.objective_profile_repository import ObjectiveProfileRepository


class CurrentMarketPositionService:
    def __init__(
        self,
        *,
        evidence_service=None,
        objective_repository=None,
        objective_profile_repository=None,
    ) -> None:
        self.evidence_service = evidence_service or CareerEvidenceService()
        self.objective_repository = (
            objective_repository or CareerObjectiveRepository()
        )
        self.objective_profile_repository = (
            objective_profile_repository or ObjectiveProfileRepository()
        )

    def build(self, candidate_id: str) -> CurrentMarketPosition:
        normalized_candidate_id = str(candidate_id or "").strip()
        if not normalized_candidate_id:
            raise ValueError("candidate_id must be non-empty.")

        evidence = self.evidence_service.build(normalized_candidate_id)
        if evidence.get("candidate_id") != normalized_candidate_id:
            raise PermissionError(
                "Career evidence belongs to another candidate."
            )

        objective = self.objective_repository.get_active(
            normalized_candidate_id
        )
        profile = self.objective_profile_repository.get_active_for_candidate(
            normalized_candidate_id
        )

        targets = []
        if objective is not None:
            if objective.candidate_id != normalized_candidate_id:
                raise PermissionError(
                    "Career objective belongs to another candidate."
                )
            targets.extend(objective.desired_role_families)

        if profile is not None:
            if profile.candidate_id != normalized_candidate_id:
                raise PermissionError(
                    "Objective profile belongs to another candidate."
                )
            targets.extend(profile.target_role_families)

        return build_current_market_position(
            candidate_id=normalized_candidate_id,
            evidence_records=evidence["records"],
            target_role_families=targets,
        )
