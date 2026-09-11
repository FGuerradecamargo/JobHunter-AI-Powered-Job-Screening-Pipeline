from models.career_intelligence_snapshot import CareerIntelligenceSnapshot
from services.career_evidence_service import CareerEvidenceService
from services.career_objective_repository import CareerObjectiveRepository
from services.current_market_position_builder import build_current_market_position
from services.database import utc_now
from services.gap_and_leverage_builder import build_gap_and_leverage_assessment
from services.improvement_plan_builder import build_improvement_plan
from services.objective_profile_repository import ObjectiveProfileRepository
from services.career_intelligence_snapshot_builder import (
    build_career_intelligence_snapshot,
)


class CareerIntelligenceSnapshotService:
    def __init__(
        self,
        *,
        evidence_service=None,
        objective_repository=None,
        objective_profile_repository=None,
        clock=utc_now,
    ) -> None:
        self.evidence_service = evidence_service or CareerEvidenceService()
        self.objective_repository = objective_repository or CareerObjectiveRepository()
        self.objective_profile_repository = (
            objective_profile_repository or ObjectiveProfileRepository()
        )
        self.clock = clock

    def build(self, candidate_id: str) -> CareerIntelligenceSnapshot:
        normalized_candidate_id = str(candidate_id or "").strip()
        if not normalized_candidate_id:
            raise ValueError("candidate_id must be non-empty.")

        evidence = self.evidence_service.build(normalized_candidate_id)
        if evidence.get("candidate_id") != normalized_candidate_id:
            raise PermissionError("Career evidence belongs to another candidate.")

        objective = self.objective_repository.get_active(normalized_candidate_id)
        if objective is not None and objective.candidate_id != normalized_candidate_id:
            raise PermissionError("Career objective belongs to another candidate.")

        profile = self.objective_profile_repository.get_active_for_candidate(
            normalized_candidate_id
        )
        if profile is not None and profile.candidate_id != normalized_candidate_id:
            raise PermissionError("Objective profile belongs to another candidate.")

        targets = []
        if objective is not None:
            targets.extend(objective.desired_role_families)
        if profile is not None:
            targets.extend(profile.target_role_families)

        position = build_current_market_position(
            candidate_id=normalized_candidate_id,
            evidence_records=evidence["records"],
            target_role_families=targets,
        )
        assessment = build_gap_and_leverage_assessment(
            candidate_id=normalized_candidate_id,
            market_signals=evidence["market_signals"],
            current_market_position=position,
        )
        plan = build_improvement_plan(
            candidate_id=normalized_candidate_id,
            assessment=assessment,
            related_objective=objective.title if objective is not None else "",
        )

        return build_career_intelligence_snapshot(
            candidate_id=normalized_candidate_id,
            generated_at=self.clock(),
            evidence_records=evidence["records"],
            objective=objective,
            current_market_position=position,
            gap_and_leverage=assessment,
            improvement_plan=plan,
        )
