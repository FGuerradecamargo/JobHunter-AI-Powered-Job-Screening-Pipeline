from dataclasses import asdict

import pytest

from models.career_evidence import CareerEvidence
from models.career_intelligence_snapshot import CareerIntelligenceSnapshot
from models.career_objective import CareerObjective
from models.current_market_position import (
    CurrentMarketPosition,
    MarketPositionRoleFamily,
)
from models.gap_and_leverage import (
    GapAndLeverageAssessment,
    LeverageOpportunity,
    MarketLeverageStrength,
    RecurringBlocker,
)
from models.improvement_plan import ImprovementPlan, ImprovementPriority
from models.objective_profile import ObjectiveProfile
from services.career_intelligence_snapshot_builder import (
    CAREER_INTELLIGENCE_SCHEMA_VERSION,
    build_career_intelligence_snapshot,
)
from services.career_intelligence_snapshot_service import (
    CareerIntelligenceSnapshotService,
)


def _record(evidence_id="e1", statement="SQL", source="job:1"):
    return CareerEvidence(
        evidence_id=evidence_id,
        evidence_type="market_signal",
        signal_type="best_match_blocker",
        source_ref=source,
        statement=statement,
        role_family="Product Operations",
        authority="market_evidence",
        metadata={"recommendation": "potential", "current_fit": 70},
    )


def _objective(objective_id="objective-a", candidate_id="candidate-a"):
    return CareerObjective(
        id=objective_id,
        candidate_id=candidate_id,
        title="Product Operations",
        description="Explicit career direction",
        desired_role_families=["Product Operations"],
    )


def _position(candidate_id="candidate-a", targets=("Product Operations",)):
    return CurrentMarketPosition(
        candidate_id=candidate_id,
        competitive_role_families=[
            MarketPositionRoleFamily(
                role_family="Product Operations",
                authority="market_evidence",
                evidence_refs=["role-e1"],
                source_refs=["job:1"],
                confidence="low",
            )
        ],
        bridge_role_families=[
            MarketPositionRoleFamily(
                role_family="Operations Analytics",
                authority="market_evidence",
            )
        ],
        target_role_families=[
            MarketPositionRoleFamily(
                role_family=target,
                authority="user_direction",
            )
            for target in targets
        ],
        best_match_count=1,
        sample_size=1,
    )


def _assessment(candidate_id="candidate-a", direction_known=True):
    return GapAndLeverageAssessment(
        candidate_id=candidate_id,
        recurring_blockers=[
            RecurringBlocker(
                blocker="SQL",
                evidence_refs=["e1", "e2"],
                source_refs=["job:1", "job:2"],
                evidence_count=2,
                independent_sources=2,
                affected_role_families=["Product Operations"],
                direction_relevance="aligned" if direction_known else "unknown",
                confidence="medium",
            ),
            RecurringBlocker(
                blocker="Direct enterprise ownership",
                gap_type="structural_distance",
                evidence_refs=["e3"],
                source_refs=["job:3"],
                evidence_count=1,
                independent_sources=1,
                affected_role_families=["Product Operations"],
                direction_relevance="aligned" if direction_known else "unknown",
                confidence="low",
            ),
        ],
        leverage_opportunities=[
            LeverageOpportunity(
                action="Create demonstrable SQL project evidence",
                rationale="Repeated raise-fit evidence.",
                expected_best_match_impact=(
                    "multiple_direction_aligned_opportunities"
                ),
                evidence_refs=["raise-e1", "raise-e2"],
                source_refs=["job:1", "job:2"],
                affected_role_families=["Product Operations"],
                direction_relevance="aligned" if direction_known else "unknown",
                confidence="medium",
            )
        ],
        market_strengths=[
            MarketLeverageStrength(
                strength="Stakeholder communication",
                evidence_refs=["strength-e1", "strength-e2"],
                source_refs=["job:1", "job:2"],
                affected_role_families=["Product Operations"],
                direction_relevance="aligned" if direction_known else "unknown",
                confidence="medium",
            )
        ],
        target_role_families=["Product Operations"] if direction_known else [],
        direction_known=direction_known,
    )


def _plan(candidate_id="candidate-a", direction_known=True):
    return ImprovementPlan(
        candidate_id=candidate_id,
        priorities=[
            ImprovementPriority(
                priority_id="priority-1",
                title="Create demonstrable SQL project evidence",
                category="evidence",
                why_now="Repeated raise-fit evidence.",
                related_objective=(
                    "Product Operations" if direction_known else ""
                ),
                direction_relevance="aligned" if direction_known else "unknown",
                affected_role_families=["Product Operations"],
                evidence_refs=["raise-e1", "raise-e2"],
                source_refs=["job:1", "job:2"],
                confidence="medium",
                priority_band="next" if direction_known else "watch",
            )
        ],
        related_objective="Product Operations" if direction_known else "",
        target_role_families=["Product Operations"] if direction_known else [],
        direction_known=direction_known,
    )


def _build(
    *,
    generated_at="2026-09-11T10:00:00Z",
    records=None,
    objective=None,
    position=None,
    assessment=None,
    plan=None,
):
    objective_value = (
        _objective()
        if objective is None
        else None if objective is False else objective
    )
    return build_career_intelligence_snapshot(
        candidate_id="candidate-a",
        generated_at=generated_at,
        evidence_records=records if records is not None else [_record()],
        objective=objective_value,
        current_market_position=position or _position(),
        gap_and_leverage=assessment or _assessment(),
        improvement_plan=plan or _plan(),
    )


def test_complete_snapshot_preserves_composed_outputs():
    position = _position()
    assessment = _assessment()
    plan = _plan()
    snapshot = _build(position=position, assessment=assessment, plan=plan)

    assert snapshot.schema_version == CAREER_INTELLIGENCE_SCHEMA_VERSION
    assert snapshot.objective_id == "objective-a"
    assert snapshot.current_market_position is position
    assert snapshot.recurring_blockers == assessment.recurring_blockers
    assert snapshot.leverage_opportunities == assessment.leverage_opportunities
    assert snapshot.improvement_priorities == plan.priorities
    assert snapshot.checkpoint_authority == "derived_decision_support"


def test_snapshot_without_objective_does_not_infer_target():
    snapshot = _build(
        objective=False,
        position=_position(targets=()),
        assessment=_assessment(direction_known=False),
        plan=_plan(direction_known=False),
    )

    assert snapshot.objective_id == ""
    assert snapshot.direction_alignment.target == []
    assert snapshot.direction_alignment.direction_known is False
    assert snapshot.direction_alignment.alignment_state == "direction_unknown"
    assert snapshot.direction_alignment.competitive_now == ["Product Operations"]


def test_direction_alignment_preserves_overlap_bridge_and_distance():
    alignment = _build().direction_alignment

    assert alignment.competitive_now == ["Product Operations"]
    assert alignment.bridge == ["Operations Analytics"]
    assert alignment.target == ["Product Operations"]
    assert alignment.competitive_target_overlap == ["Product Operations"]
    assert alignment.distance_signals == ["Direct enterprise ownership"]
    assert alignment.alignment_state == "competitive_overlap_observed"


def test_competitive_advantage_requires_market_support():
    assessment = _assessment()
    assessment = GapAndLeverageAssessment(
        candidate_id=assessment.candidate_id,
        market_strengths=[
            *assessment.market_strengths,
            MarketLeverageStrength(
                strength="Self-described leadership",
                evidence_refs=[],
                source_refs=[],
                confidence="high",
            ),
        ],
    )
    advantages = _build(assessment=assessment).competitive_advantages

    assert [item.signal for item in advantages] == [
        "Stakeholder communication"
    ]
    assert advantages[0].evidence_refs == ["strength-e1", "strength-e2"]
    assert advantages[0].evidence_count == 2
    assert advantages[0].confidence == "medium"


def test_objective_change_changes_source_signature():
    first = _build(objective=_objective("objective-a"))
    second = _build(objective=_objective("objective-b"))

    assert first.source_signature != second.source_signature


def test_market_evidence_change_changes_source_signature():
    first = _build(records=[_record(statement="SQL")])
    second = _build(records=[_record(statement="Python")])

    assert first.source_signature != second.source_signature


def test_source_order_and_generated_at_do_not_change_signature():
    records = [_record("e1", "SQL", "job:1"), _record("e2", "CRM", "job:2")]
    first = _build(records=records, generated_at="2026-09-11T10:00:00Z")
    second = _build(
        records=list(reversed(records)),
        generated_at="2026-09-12T10:00:00Z",
    )

    assert first.source_signature == second.source_signature
    assert first.generated_at != second.generated_at


def test_fixed_inputs_have_deterministic_serialization():
    first = _build()
    second = _build()

    assert asdict(first) == asdict(second)


def test_empty_market_history_is_valid():
    snapshot = _build(
        records=[],
        position=CurrentMarketPosition(candidate_id="candidate-a"),
        assessment=GapAndLeverageAssessment(candidate_id="candidate-a"),
        plan=ImprovementPlan(candidate_id="candidate-a"),
    )

    assert snapshot.competitive_advantages == []
    assert snapshot.recurring_blockers == []
    assert snapshot.improvement_priorities == []


class FakeEvidenceService:
    def __init__(self, candidate_id="candidate-a"):
        self.candidate_id = candidate_id

    def build(self, candidate_id):
        return {
            "candidate_id": self.candidate_id,
            "records": [_record()],
            "market_signals": [],
        }


class FakeObjectiveRepository:
    def __init__(self, objective=None):
        self.objective = objective

    def get_active(self, candidate_id):
        return self.objective


class FakeProfileRepository:
    def __init__(self, profile=None):
        self.profile = profile

    def get_active_for_candidate(self, candidate_id):
        return self.profile


def _snapshot_service(
    *,
    evidence_candidate="candidate-a",
    objective_candidate="candidate-a",
    profile_candidate="candidate-a",
):
    return CareerIntelligenceSnapshotService(
        evidence_service=FakeEvidenceService(evidence_candidate),
        objective_repository=FakeObjectiveRepository(
            _objective(candidate_id=objective_candidate)
        ),
        objective_profile_repository=FakeProfileRepository(
            ObjectiveProfile(
                candidate_id=profile_candidate,
                objective_id="objective-a",
                target_role_families=["Product Operations"],
            )
        ),
        clock=lambda: "2026-09-11T10:00:00Z",
    )


@pytest.mark.parametrize(
    (
        "evidence_candidate",
        "objective_candidate",
        "profile_candidate",
    ),
    [
        ("candidate-b", "candidate-a", "candidate-a"),
        ("candidate-a", "candidate-b", "candidate-a"),
        ("candidate-a", "candidate-a", "candidate-b"),
    ],
)
def test_service_rejects_cross_candidate_dependencies(
    evidence_candidate,
    objective_candidate,
    profile_candidate,
):
    service = _snapshot_service(
        evidence_candidate=evidence_candidate,
        objective_candidate=objective_candidate,
        profile_candidate=profile_candidate,
    )

    with pytest.raises(PermissionError):
        service.build("candidate-a")


def test_service_returns_snapshot_without_ai_dependency():
    snapshot = _snapshot_service().build("candidate-a")

    assert isinstance(snapshot, CareerIntelligenceSnapshot)
    assert snapshot.generated_at == "2026-09-11T10:00:00Z"


def test_snapshot_service_reads_each_source_once():
    evidence_service = FakeEvidenceService()
    objective_repository = FakeObjectiveRepository(_objective())
    profile_repository = FakeProfileRepository(
        ObjectiveProfile(
            candidate_id="candidate-a",
            objective_id="objective-a",
            target_role_families=["Product Operations"],
        )
    )
    evidence_service.calls = 0
    objective_repository.calls = 0
    profile_repository.calls = 0

    original_evidence_build = evidence_service.build
    original_objective_get = objective_repository.get_active
    original_profile_get = profile_repository.get_active_for_candidate

    def evidence_build(candidate_id):
        evidence_service.calls += 1
        return original_evidence_build(candidate_id)

    def objective_get(candidate_id):
        objective_repository.calls += 1
        return original_objective_get(candidate_id)

    def profile_get(candidate_id):
        profile_repository.calls += 1
        return original_profile_get(candidate_id)

    evidence_service.build = evidence_build
    objective_repository.get_active = objective_get
    profile_repository.get_active_for_candidate = profile_get

    service = CareerIntelligenceSnapshotService(
        evidence_service=evidence_service,
        objective_repository=objective_repository,
        objective_profile_repository=profile_repository,
        clock=lambda: "2026-09-11T10:00:00Z",
    )
    service.build("candidate-a")

    assert evidence_service.calls == 1
    assert objective_repository.calls == 1
    assert profile_repository.calls == 1
