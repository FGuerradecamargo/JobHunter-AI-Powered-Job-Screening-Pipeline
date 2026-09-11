import pytest

from models.career_evidence import CareerEvidence
from models.career_evidence_signal import CareerEvidenceSignal
from models.current_market_position import (
    CurrentMarketPosition,
    MarketPositionRoleFamily,
)
from services.career_evidence_aggregator import aggregate_market_evidence
from services.gap_and_leverage_builder import build_gap_and_leverage_assessment
from services.gap_and_leverage_service import GapAndLeverageService


def _signal(
    signal_type,
    statement,
    sources,
    roles,
    confidence="medium",
):
    return CareerEvidenceSignal(
        signal_id=f"signal:{signal_type}:{statement}",
        signal_type=signal_type,
        statement=statement,
        evidence_refs=[f"e:{source}" for source in sources],
        source_refs=list(sources),
        role_families=list(roles),
        evidence_count=len(sources),
        independent_sources=len(sources),
        sample_size=max(2, len(sources)),
        frequency=1.0,
        confidence=confidence,
    )


def _position(targets=()):
    return CurrentMarketPosition(
        candidate_id="candidate-a",
        target_role_families=[
            MarketPositionRoleFamily(
                role_family=target,
                authority="user_direction",
            )
            for target in targets
        ],
    )


def _build(signals, targets=("Product Operations",)):
    return build_gap_and_leverage_assessment(
        candidate_id="candidate-a",
        market_signals=signals,
        current_market_position=_position(targets),
    )


def test_recurring_blocker_preserves_support_across_roles():
    assessment = _build(
        [
            _signal(
                "best_match_blocker",
                "SQL",
                ["job:1", "job:2"],
                ["Product Operations", "Operations Analytics"],
            )
        ]
    )
    blocker = assessment.recurring_blockers[0]

    assert blocker.independent_sources == 2
    assert blocker.affected_role_families == [
        "Product Operations",
        "Operations Analytics",
    ]
    assert blocker.evidence_refs == ["e:job:1", "e:job:2"]
    assert blocker.confidence == "medium"
    assert blocker.direction_relevance == "aligned"


def test_one_off_blocker_remains_low_confidence_without_leverage():
    assessment = _build(
        [
            _signal(
                "best_match_blocker",
                "Unusual vendor tool",
                ["job:1"],
                ["Product Operations"],
                confidence="low",
            ),
            _signal(
                "raise_fit",
                "Create unusual vendor demo",
                ["job:1"],
                ["Product Operations"],
                confidence="low",
            ),
        ]
    )

    assert assessment.recurring_blockers[0].confidence == "low"
    assert assessment.leverage_opportunities == []


def test_direction_relevant_blocker_is_prioritized_without_changing_confidence():
    signals = [
        _signal(
            "best_match_blocker",
            "Support tooling",
            ["job:1", "job:2"],
            ["Customer Support"],
        ),
        _signal(
            "best_match_blocker",
            "SQL",
            ["job:3", "job:4"],
            ["Product Operations"],
        ),
    ]
    assessment = _build(signals)

    assert [item.blocker for item in assessment.recurring_blockers] == [
        "SQL",
        "Support tooling",
    ]
    assert assessment.recurring_blockers[0].confidence == "medium"
    assert assessment.recurring_blockers[1].confidence == "medium"
    assert assessment.recurring_blockers[1].direction_relevance == "unrelated"


def test_competitiveness_never_becomes_target_direction():
    assessment = _build(
        [
            _signal(
                "market_strength",
                "Customer empathy",
                ["job:1", "job:2"],
                ["Customer Support"],
            )
        ],
        targets=(),
    )

    assert assessment.direction_known is False
    assert assessment.target_role_families == []
    assert assessment.market_strengths[0].direction_relevance == "unknown"


def test_repeated_actionable_raise_fit_forms_leverage():
    assessment = _build(
        [
            _signal(
                "raise_fit",
                "Create demonstrable SQL project evidence",
                ["job:1", "job:2", "job:3"],
                ["Product Operations", "Operations Analytics"],
                confidence="high",
            )
        ]
    )
    item = assessment.leverage_opportunities[0]

    assert item.action == "Create demonstrable SQL project evidence"
    assert item.leverage_type == "evidence_development"
    assert item.expected_best_match_impact == (
        "multiple_direction_aligned_opportunities"
    )
    assert item.confidence == "high"
    assert item.evidence_refs == ["e:job:1", "e:job:2", "e:job:3"]


@pytest.mark.parametrize(
    "statement",
    [
        "5 years enterprise Kubernetes experience",
        "Direct fraud investigation experience",
        "Production cloud experience",
    ],
)
def test_structural_raise_fit_does_not_become_fake_action(statement):
    assessment = _build(
        [
            _signal(
                "raise_fit",
                statement,
                ["job:1", "job:2"],
                ["Product Operations"],
            )
        ]
    )

    assert assessment.leverage_opportunities == []
    assert assessment.recurring_blockers[0].blocker == statement
    assert assessment.recurring_blockers[0].gap_type == "structural_distance"


def test_market_strength_is_not_treated_as_blocker():
    assessment = _build(
        [
            _signal(
                "market_strength",
                "Stakeholder communication",
                ["job:1", "job:2"],
                ["Product Operations"],
            )
        ]
    )

    assert assessment.recurring_blockers == []
    assert assessment.market_strengths[0].strength == (
        "Stakeholder communication"
    )


def test_duplicate_job_does_not_inflate_support():
    records = [
        CareerEvidence(
            evidence_id=evidence_id,
            evidence_type="market_signal",
            signal_type="best_match_blocker",
            source_ref="job:1",
            statement="SQL",
            role_family="Product Operations",
            authority="market_evidence",
            metadata={"recommendation": "potential", "current_fit": 70},
        )
        for evidence_id in ("e1", "e2")
    ]
    assessment = _build(aggregate_market_evidence(records))

    assert assessment.recurring_blockers[0].independent_sources == 1
    assert assessment.recurring_blockers[0].source_refs == ["job:1"]


def test_empty_market_history_and_missing_direction_are_valid():
    assessment = _build([], targets=())

    assert assessment.direction_known is False
    assert assessment.recurring_blockers == []
    assert assessment.leverage_opportunities == []
    assert assessment.market_strengths == []


class FakeEvidenceService:
    def __init__(self, candidate_id):
        self.candidate_id = candidate_id

    def build(self, candidate_id):
        return {"candidate_id": self.candidate_id, "market_signals": []}


class FakePositionService:
    def __init__(self, candidate_id):
        self.candidate_id = candidate_id

    def build(self, candidate_id):
        return CurrentMarketPosition(candidate_id=self.candidate_id)


@pytest.mark.parametrize(
    ("evidence_candidate", "position_candidate"),
    [("candidate-b", "candidate-a"), ("candidate-a", "candidate-b")],
)
def test_service_rejects_cross_candidate_dependencies(
    evidence_candidate,
    position_candidate,
):
    service = GapAndLeverageService(
        evidence_service=FakeEvidenceService(evidence_candidate),
        market_position_service=FakePositionService(position_candidate),
    )

    with pytest.raises(PermissionError):
        service.build("candidate-a")
