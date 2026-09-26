from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from services.candidate_market_service import CandidateMarketService
from models.candidate_market import (
    CandidateMarketState,
    ImprovementBand,
    ImprovementKind,
)
from models.hiring_case import RequirementImportance
from models.market_profile import (
    MarketConfidence,
    MarketPattern,
    MarketProfile,
    MarketSegment,
)
from models.profile_interpretation import (
    CandidateProfileSnapshot,
    ProfileCapability,
    ProfileCheckpoint,
)
from services.candidate_market_builder import (
    build_candidate_market,
    build_improvement_plan,
)


def candidate(*, objectives=("Operations",), gaps=(), evidence_gaps=()):
    return CandidateProfileSnapshot(
        candidate_id="c",
        profile_version=2,
        memory_signature="sig",
        created_at="2026-09-26T00:00:00+00:00",
        source_refs=("exp:1", "exp:2"),
        capabilities=(
            ProfileCapability(
                "sql",
                "SQL",
                ("exp:1",),
                transferable=False,
            ),
            ProfileCapability(
                "stakeholders",
                "Stakeholder management",
                ("exp:2",),
                transferable=True,
            ),
        ),
        checkpoint=ProfileCheckpoint(
            current_position="Operations specialist",
        ),
        confirmed_gaps=gaps,
        evidence_gaps=evidence_gaps,
        objectives=objectives,
    )


def market():
    patterns = (
        MarketPattern(
            "capability",
            "SQL",
            7,
            10,
            tuple(f"j{i}" for i in range(7)),
            0.7,
            MarketConfidence.HIGH,
        ),
        MarketPattern(
            "capability",
            "Stakeholder management",
            6,
            10,
            tuple(f"s{i}" for i in range(6)),
            0.6,
            MarketConfidence.HIGH,
        ),
        MarketPattern(
            "capability",
            "Python",
            5,
            10,
            tuple(f"p{i}" for i in range(5)),
            0.5,
            MarketConfidence.HIGH,
        ),
    )
    return MarketProfile(
        profile_version=4,
        source_signature="market-sig",
        created_at="2026-09-26T00:00:00+00:00",
        segment=MarketSegment(role_family="Operations"),
        sample_size=10,
        patterns=patterns,
    )


def test_candidate_market_does_not_mutate_market_or_candidate_truth():
    c = candidate()
    m = market()
    result = build_candidate_market(
        candidate_profile=c,
        market_profile=m,
    )
    states = {item.label: item.state for item in result.signals}
    assert states["SQL"] is CandidateMarketState.PROVEN
    assert states["Stakeholder management"] is CandidateMarketState.TRANSFERABLE
    assert states["Python"] is CandidateMarketState.EVIDENCE_MISSING
    assert c.capabilities[0].label == "SQL"
    assert m.sample_size == 10


def test_confirmed_gap_can_create_build_but_missing_evidence_cannot():
    c = candidate(gaps=("Python",))
    assessment = build_candidate_market(
        candidate_profile=c,
        market_profile=market(),
    )
    plan = build_improvement_plan(
        assessment,
        evidence_gap_labels=c.evidence_gaps,
    )
    python = next(
        item for item in plan.improvements
        if item.label == "Python"
    )
    assert python.kind is ImprovementKind.BUILD
    assert python.band is ImprovementBand.NOW


def test_transferable_capability_creates_prove_not_build():
    c = candidate()
    assessment = build_candidate_market(
        candidate_profile=c,
        market_profile=market(),
    )
    plan = build_improvement_plan(assessment)
    item = next(
        x for x in plan.improvements
        if x.label == "Stakeholder management"
    )
    assert item.kind is ImprovementKind.PROVE


def test_unknown_capability_is_explore_not_assumed_gap():
    c = candidate()
    assessment = build_candidate_market(
        candidate_profile=c,
        market_profile=market(),
    )
    plan = build_improvement_plan(assessment)
    python = next(
        item for item in plan.improvements
        if item.label == "Python"
    )
    assert python.kind is ImprovementKind.EXPLORE


def test_explicit_evidence_gap_can_create_prove():
    c = candidate(evidence_gaps=("Python",))
    assessment = build_candidate_market(
        candidate_profile=c,
        market_profile=market(),
    )
    plan = build_improvement_plan(
        assessment,
        evidence_gap_labels=c.evidence_gaps,
    )
    python = next(
        item for item in plan.improvements
        if item.label == "Python"
    )
    assert python.kind is ImprovementKind.PROVE


def test_unknown_direction_pushes_improvement_to_watch():
    c = candidate(objectives=())
    assessment = build_candidate_market(
        candidate_profile=c,
        market_profile=market(),
    )
    plan = build_improvement_plan(assessment)
    assert all(
        item.band is ImprovementBand.WATCH
        for item in plan.improvements
    )


def test_unrelated_objective_does_not_imply_segment_alignment():
    assessment = build_candidate_market(candidate_profile=candidate(objectives=("Nursing",)), market_profile=market())
    assert assessment.direction_known
    assert all(s.direction_relevance == "unknown" for s in assessment.signals)
    assert all(i.band is ImprovementBand.WATCH for i in build_improvement_plan(assessment).improvements)


def test_direction_alias_uses_existing_role_family_normalization():
    profile = replace(market(), segment=MarketSegment(role_family="Product Operations"))
    assessment = build_candidate_market(candidate_profile=candidate(objectives=("Product Ops",)), market_profile=profile)
    assert all(s.direction_relevance == "aligned" for s in assessment.signals)


def test_explicit_evidence_gap_is_carried_without_side_channel():
    assessment = build_candidate_market(candidate_profile=candidate(evidence_gaps=("Python",)), market_profile=market())
    plan = build_improvement_plan(assessment)
    assert next(i for i in plan.improvements if i.label == "Python").kind is ImprovementKind.PROVE
    with pytest.raises(ValueError):
        build_improvement_plan(assessment, evidence_gap_labels=("Invented",))


def test_conflicting_gap_and_capability_is_not_build_and_order_is_stable():
    c = candidate(gaps=("SQL",))
    assessment = build_candidate_market(candidate_profile=c, market_profile=market())
    assert next(s for s in assessment.signals if s.label == "SQL").state is CandidateMarketState.EVIDENCE_MISSING
    assert next(i for i in build_improvement_plan(assessment).improvements if i.label == "SQL").kind is ImprovementKind.EXPLORE
    c = candidate()
    c = replace(c, capabilities=c.capabilities + (replace(c.capabilities[0], transferable=True),))
    one = build_candidate_market(candidate_profile=c, market_profile=market())
    two = build_candidate_market(candidate_profile=replace(c, capabilities=tuple(reversed(c.capabilities))), market_profile=market())
    assert one == two
    assert one.signals[0].state is CandidateMarketState.PROVEN


def test_relationship_keeps_versions_signatures_and_inputs_unchanged():
    c, m = candidate(), market()
    before = asdict(c), asdict(m)
    assessment = build_candidate_market(candidate_profile=c, market_profile=m)
    plan = build_improvement_plan(assessment)
    assert (asdict(c), asdict(m)) == before
    assert plan.candidate_id == c.candidate_id
    assert plan.candidate_memory_signature == c.memory_signature
    assert plan.market_source_signature == m.source_signature
    assert plan.candidate_profile_version == c.profile_version
    assert plan.market_profile_version == m.profile_version


def test_small_and_empty_market_do_not_invent_priorities():
    m = replace(market(), patterns=tuple(replace(p, confidence=MarketConfidence.LOW) for p in market().patterns))
    plan = build_improvement_plan(build_candidate_market(candidate_profile=candidate(), market_profile=m))
    assert all(i.band is ImprovementBand.WATCH for i in plan.improvements)
    m = replace(m, patterns=(), sample_size=0)
    assert build_candidate_market(candidate_profile=candidate(), market_profile=m).signals == ()


def test_service_checks_scope_and_does_not_fallback_or_mutate():
    c, m = candidate(), market()
    service = CandidateMarketService(
        candidate_repository=SimpleNamespace(current_candidate=lambda cid: c),
        market_repository=SimpleNamespace(current=lambda segment: m),
    )
    assessment, plan = service.build("c", m.segment)
    assert assessment.candidate_id == plan.candidate_id == "c"
    with pytest.raises(PermissionError):
        service.build("other", m.segment)
    with pytest.raises(ValueError):
        service.build("c", MarketSegment(role_family="Nursing"))
    service.markets = SimpleNamespace(current=lambda segment: None)
    with pytest.raises(ValueError, match="Global market"):
        service.build("c", m.segment)


def test_two_candidates_share_market_without_cross_candidate_changes():
    m = market()
    a, b = candidate(gaps=("Python",)), replace(candidate(), candidate_id="other")
    before = asdict(m)
    aa = build_candidate_market(candidate_profile=a, market_profile=m)
    bb = build_candidate_market(candidate_profile=b, market_profile=m)
    assert next(s for s in aa.signals if s.label == "Python").state is CandidateMarketState.CONFIRMED_GAP
    assert next(s for s in bb.signals if s.label == "Python").state is CandidateMarketState.EVIDENCE_MISSING
    assert asdict(m) == before
