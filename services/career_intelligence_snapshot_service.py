from models.career_intelligence_snapshot import CareerIntelligenceSnapshot
from services.career_evidence_service import CareerEvidenceService
from services.career_objective_repository import CareerObjectiveRepository
from services.current_market_position_service import CurrentMarketPositionService
from services.database import utc_now
from services.gap_and_leverage_service import GapAndLeverageService
from services.improvement_plan_service import ImprovementPlanService
from services.career_intelligence_snapshot_builder import (
    build_career_intelligence_snapshot,
)


class CareerIntelligenceSnapshotService:
    def __init__(
        self,
        *,
        evidence_service=None,
        objective_repository=None,
        market_position_service=None,
        gap_and_leverage_service=None,
        improvement_plan_service=None,
        clock=utc_now,
    ) -> None:
        self.evidence_service = evidence_service or CareerEvidenceService()
        self.objective_repository = objective_repository or CareerObjectiveRepository()
        self.market_position_service = (
            market_position_service or CurrentMarketPositionService()
        )
        self.gap_and_leverage_service = (
            gap_and_leverage_service or GapAndLeverageService()
        )
        self.improvement_plan_service = (
            improvement_plan_service or ImprovementPlanService()
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
        position = self.market_position_service.build(normalized_candidate_id)
        assessment = self.gap_and_leverage_service.build(normalized_candidate_id)
        plan = self.improvement_plan_service.build(normalized_candidate_id)

        return build_career_intelligence_snapshot(
            candidate_id=normalized_candidate_id,
            generated_at=self.clock(),
            evidence_records=evidence["records"],
            objective=objective,
            current_market_position=position,
            gap_and_leverage=assessment,
            improvement_plan=plan,
        )
