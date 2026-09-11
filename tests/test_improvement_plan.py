import pytest

from models.career_objective import CareerObjective
from models.gap_and_leverage import (
    GapAndLeverageAssessment,
    LeverageOpportunity,
    MarketLeverageStrength,
    RecurringBlocker,
)
from services.improvement_plan_builder import build_improvement_plan
from services.improvement_plan_service import ImprovementPlanService


def _leverage(
    action,
    *,
    relevance="aligned",
    confidence="high",
    sources=("job:1", "job:2"),
    roles=("Product Operations",),
):
    return LeverageOpportunity(
        action=action,
        rationale="Repeated raise-fit evidence.",
        expected_best_match_impact="multiple_observed_opportunities",
        evidence_refs=[f"e:{source}" for source in sources],
        source_refs=list(sources),
        affected_role_families=list(roles),
        direction_relevance=relevance,
        confidence=confidence,
    )


def _assessment(
    *,
    leverage=(),
    blockers=(),
    strengths=(),
    direction_known=True,
    targets=("Product Operations",),
    candidate_id="candidate-a",
):
    return GapAndLeverageAssessment(
        candidate_id=candidate_id,
        recurring_blockers=list(blockers),
        leverage_opportunities=list(leverage),
        market_strengths=list(strengths),
        target_role_families=list(targets),
        direction_known=direction_known,
    )


def _build(assessment, objective="Move into Product Operations"):
    return build_improvement_plan(
        candidate_id="candidate-a",
        assessment=assessment,
        related_objective=objective,
    )


def test_aligned_high_confidence_leverage_becomes_now():
    plan = _build(
        _assessment(
            leverage=[_leverage("Create demonstrable SQL project evidence")]
        )
    )
    priority = plan.priorities[0]

    assert priority.priority_band == "now"
    assert priority.category == "evidence"
    assert priority.related_objective == "Move into Product Operations"
    assert priority.evidence_refs == ["e:job:1", "e:job:2"]
    assert priority.source_refs == ["job:1", "job:2"]
    assert priority.affected_role_families == ["Product Operations"]
    assert priority.confidence == "high"


def test_unrelated_leverage_does_not_become_now():
    plan = _build(
        _assessment(
            leverage=[
                _leverage(
                    "Create support tooling portfolio",
                    relevance="unrelated",
                    roles=("Customer Support",),
                )
            ]
        )
    )

    assert plan.priorities[0].priority_band == "watch"
    assert plan.priorities[0].related_objective == ""


def test_unknown_direction_generates_exploration_not_prescription():
    plan = _build(
        _assessment(
            leverage=[
                _leverage(
                    "Create demonstrable SQL project evidence",
                    relevance="unknown",
                )
            ],
            direction_known=False,
            targets=(),
        )
    )
    priority = plan.priorities[0]

    assert priority.direction_relevance == "unknown"
    assert priority.category == "exploration"
    assert priority.priority_band == "watch"
    assert priority.related_objective == ""
    assert plan.related_objective == ""


def test_structural_distance_is_watch_not_short_term_action():
    blocker = RecurringBlocker(
        blocker="5 years enterprise Kubernetes experience",
        gap_type="structural_distance",
        evidence_refs=["e1", "e2"],
        source_refs=["job:1", "job:2"],
        affected_role_families=["Product Operations"],
        direction_relevance="aligned",
        confidence="medium",
    )
    priority = _build(_assessment(blockers=[blocker])).priorities[0]

    assert priority.priority_band == "watch"
    assert priority.category == "exploration"
    assert priority.title.startswith("Monitor structural distance:")


def test_low_confidence_leverage_is_not_top_priority():
    plan = _build(
        _assessment(
            leverage=[
                _leverage(
                    "Create narrow tool demo",
                    confidence="low",
                    sources=("job:1",),
                )
            ]
        )
    )

    assert plan.priorities[0].priority_band == "watch"


def test_repeated_broad_leverage_outranks_narrow_leverage():
    broad = _leverage(
        "Create SQL evidence",
        confidence="medium",
        sources=("job:1", "job:2", "job:3"),
        roles=("Product Operations", "Operations Analytics"),
    )
    narrow = _leverage(
        "Create CRM evidence",
        confidence="medium",
        sources=("job:4", "job:5"),
    )
    plan = _build(_assessment(leverage=[narrow, broad]))

    assert [item.title for item in plan.priorities] == [
        "Create SQL evidence",
        "Create CRM evidence",
    ]


def test_explicit_target_remains_without_current_competitiveness():
    plan = _build(
        _assessment(leverage=[], targets=("Future AI Operations",))
    )

    assert plan.target_role_families == ["Future AI Operations"]
    assert plan.related_objective == "Move into Product Operations"
    assert plan.priorities == []


def test_competitive_market_signal_cannot_invent_objective():
    strength = MarketLeverageStrength(
        strength="Customer empathy",
        source_refs=["job:1", "job:2"],
        direction_relevance="unknown",
        confidence="high",
    )
    plan = _build(
        _assessment(
            strengths=[strength],
            direction_known=False,
            targets=(),
        )
    )

    assert plan.related_objective == ""
    assert plan.target_role_families == []
    assert plan.priorities == []


def test_high_confidence_aligned_strength_can_be_amplified_next():
    strength = MarketLeverageStrength(
        strength="Stakeholder communication",
        evidence_refs=["e1", "e2"],
        source_refs=["job:1", "job:2"],
        affected_role_families=["Product Operations"],
        direction_relevance="aligned",
        confidence="high",
    )
    priority = _build(_assessment(strengths=[strength])).priorities[0]

    assert priority.priority_band == "next"
    assert priority.category == "evidence"
    assert priority.evidence_refs == ["e1", "e2"]


def test_ordering_is_stable_regardless_of_input_order():
    first = _leverage("Create SQL evidence", confidence="medium")
    second = _leverage("Build automation portfolio", confidence="medium")

    forward = _build(_assessment(leverage=[first, second]))
    reverse = _build(_assessment(leverage=[second, first]))

    assert [item.priority_id for item in forward.priorities] == [
        item.priority_id for item in reverse.priorities
    ]


def test_empty_assessment_is_valid():
    plan = _build(_assessment(leverage=[], blockers=[], strengths=[]))

    assert plan.priorities == []
    assert plan.checkpoint_authority == "decision_support"


class FakeAssessmentService:
    def __init__(self, candidate_id="candidate-a", direction_known=True):
        self.candidate_id = candidate_id
        self.direction_known = direction_known

    def build(self, candidate_id):
        return _assessment(
            candidate_id=self.candidate_id,
            direction_known=self.direction_known,
            targets=("Product Operations",) if self.direction_known else (),
        )


class FakeObjectiveRepository:
    def __init__(self, objective=None):
        self.objective = objective

    def get_active(self, candidate_id):
        return self.objective


def _objective(candidate_id="candidate-a"):
    return CareerObjective(
        id="objective-a",
        candidate_id=candidate_id,
        title="Product Operations",
        description="Explicit direction",
        desired_role_families=["Product Operations"],
    )


@pytest.mark.parametrize(
    ("assessment_candidate", "objective_candidate"),
    [("candidate-b", "candidate-a"), ("candidate-a", "candidate-b")],
)
def test_service_rejects_cross_candidate_dependencies(
    assessment_candidate,
    objective_candidate,
):
    service = ImprovementPlanService(
        assessment_service=FakeAssessmentService(assessment_candidate),
        objective_repository=FakeObjectiveRepository(_objective(objective_candidate)),
    )

    with pytest.raises(PermissionError):
        service.build("candidate-a")


def test_service_allows_missing_objective_without_inventing_one():
    service = ImprovementPlanService(
        assessment_service=FakeAssessmentService(direction_known=False),
        objective_repository=FakeObjectiveRepository(),
    )

    assert service.build("candidate-a").related_objective == ""

