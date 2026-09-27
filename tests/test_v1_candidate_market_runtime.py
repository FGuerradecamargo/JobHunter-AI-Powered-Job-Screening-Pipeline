from pathlib import Path
from types import SimpleNamespace

from models.market_profile import (
    MarketConfidence,
    MarketPattern,
    MarketProfile,
    MarketSegment,
)
from models.profile_interpretation import (
    CandidateProfileSnapshot,
    ProfileCheckpoint,
)
from services.candidate_market_runtime import (
    load_candidate_market_runtime,
)


def candidate(objectives=("Product Ops",)):
    return CandidateProfileSnapshot(
        candidate_id="candidate-1",
        profile_version=1,
        memory_signature="candidate-sig",
        created_at="2026-09-27T00:00:00+00:00",
        source_refs=("experience:1",),
        capabilities=(),
        checkpoint=ProfileCheckpoint(
            current_position="Operations specialist",
        ),
        objectives=objectives,
    )


def market():
    return MarketProfile(
        profile_version=1,
        source_signature="market-sig",
        created_at="2026-09-27T00:00:00+00:00",
        segment=MarketSegment(
            role_family="Product Operations",
        ),
        sample_size=8,
        patterns=(
            MarketPattern(
                dimension="capability",
                label="SQL",
                independent_jobs=5,
                sample_size=8,
                source_job_ids=("1", "2", "3", "4", "5"),
                frequency=0.625,
                confidence=MarketConfidence.HIGH,
            ),
        ),
    )


def test_runtime_matches_role_family_alias_without_legacy_fallback():
    profile = candidate()
    profile_market = market()

    candidates = SimpleNamespace(
        current_candidate=lambda candidate_id: profile
    )

    markets = SimpleNamespace(
        list_current=lambda: (profile_market,),
        current=lambda segment: (
            profile_market
            if segment == profile_market.segment
            else None
        ),
    )

    result = load_candidate_market_runtime(
        "candidate-1",
        candidate_repository=candidates,
        market_repository=markets,
    )

    assert result["status"] == "ok"
    assert len(result["segments"]) == 1

    entry = result["segments"][0]

    assert entry["assessment"].candidate_id == "candidate-1"
    assert entry["plan"].market_profile_version == 1
    assert entry["plan"].candidate_profile_version == 1


def test_runtime_does_not_invent_direction_or_market():
    candidates = SimpleNamespace(
        current_candidate=lambda candidate_id: candidate(objectives=())
    )
    markets = SimpleNamespace(
        list_current=lambda: (),
        current=lambda segment: None,
    )

    result = load_candidate_market_runtime(
        "candidate-1",
        candidate_repository=candidates,
        market_repository=markets,
    )

    assert result["status"] == "direction_unavailable"

    candidates.current_candidate = lambda candidate_id: candidate()

    result = load_candidate_market_runtime(
        "candidate-1",
        candidate_repository=candidates,
        market_repository=markets,
    )

    assert result["status"] == "market_unavailable"


def test_improvements_page_uses_official_candidate_market_only():
    source = Path("pages/4_Improvements.py").read_text(
        encoding="utf-8"
    )

    assert "load_candidate_market_runtime" in source
    assert "career_intelligence_presenter" not in source
    assert "CareerIntelligenceSnapshotService" not in source
    assert "CurrentMarketPositionService" not in source
    assert "ImprovementPlanService" not in source
