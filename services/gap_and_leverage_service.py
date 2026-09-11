from models.gap_and_leverage import GapAndLeverageAssessment
from services.career_evidence_service import CareerEvidenceService
from services.current_market_position_service import CurrentMarketPositionService
from services.gap_and_leverage_builder import build_gap_and_leverage_assessment


class GapAndLeverageService:
    def __init__(self, *, evidence_service=None, market_position_service=None):
        self.evidence_service = evidence_service or CareerEvidenceService()
        self.market_position_service = (
            market_position_service or CurrentMarketPositionService()
        )

    def build(self, candidate_id: str) -> GapAndLeverageAssessment:
        normalized_candidate_id = str(candidate_id or "").strip()
        if not normalized_candidate_id:
            raise ValueError("candidate_id must be non-empty.")

        evidence = self.evidence_service.build(normalized_candidate_id)
        if evidence.get("candidate_id") != normalized_candidate_id:
            raise PermissionError("Career evidence belongs to another candidate.")

        position = self.market_position_service.build(normalized_candidate_id)
        if position.candidate_id != normalized_candidate_id:
            raise PermissionError("Current market position belongs to another candidate.")

        return build_gap_and_leverage_assessment(
            candidate_id=normalized_candidate_id,
            market_signals=evidence["market_signals"],
            current_market_position=position,
        )
