from models.improvement_plan import ImprovementPlan
from services.career_objective_repository import CareerObjectiveRepository
from services.gap_and_leverage_service import GapAndLeverageService
from services.improvement_plan_builder import build_improvement_plan


class ImprovementPlanService:
    def __init__(self, *, assessment_service=None, objective_repository=None):
        self.assessment_service = assessment_service or GapAndLeverageService()
        self.objective_repository = objective_repository or CareerObjectiveRepository()

    def build(self, candidate_id: str) -> ImprovementPlan:
        normalized_candidate_id = str(candidate_id or "").strip()
        if not normalized_candidate_id:
            raise ValueError("candidate_id must be non-empty.")

        assessment = self.assessment_service.build(normalized_candidate_id)
        if assessment.candidate_id != normalized_candidate_id:
            raise PermissionError("Gap and leverage assessment belongs to another candidate.")

        objective = self.objective_repository.get_active(normalized_candidate_id)
        if objective is not None and objective.candidate_id != normalized_candidate_id:
            raise PermissionError("Career objective belongs to another candidate.")

        return build_improvement_plan(
            candidate_id=normalized_candidate_id,
            assessment=assessment,
            related_objective=objective.title if objective is not None else "",
        )
