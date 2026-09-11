from models.career_intelligence_snapshot import (
    CareerIntelligenceSnapshot,
    CompetitiveAdvantage,
    DirectionAlignment,
)
from models.current_market_position import CurrentMarketPosition
from models.gap_and_leverage import RecurringBlocker
from models.improvement_plan import ImprovementPriority
from services.career_intelligence_presenter import (
    CONFIDENCE_EXPLANATION,
    build_career_intelligence_view,
    load_career_intelligence_snapshot,
)


def _priority(
    title,
    *,
    band="now",
    relevance="aligned",
    confidence="high",
):
    return ImprovementPriority(
        priority_id=f"priority:{title}",
        title=title,
        category="evidence",
        why_now="Repeated market support.",
        related_objective=(
            "Product Operations" if relevance == "aligned" else ""
        ),
        direction_relevance=relevance,
        affected_role_families=["Product Operations"],
        evidence_refs=["e1", "e2"],
        source_refs=["job:1", "job:2"],
        confidence=confidence,
        priority_band=band,
    )


def _snapshot(
    *,
    sample_size=2,
    target=("Product Operations",),
    priorities=(),
    blockers=(),
):
    return CareerIntelligenceSnapshot(
        candidate_id="candidate-a",
        objective_id="objective-a" if target else "",
        schema_version="career-intelligence-v1",
        generated_at="2026-09-11T10:00:00Z",
        source_signature="signature",
        current_market_position=CurrentMarketPosition(
            candidate_id="candidate-a",
            average_fit=72.5 if sample_size else None,
            best_match_count=1 if sample_size else 0,
            near_match_count=1 if sample_size else 0,
            sample_size=sample_size,
        ),
        competitive_advantages=[
            CompetitiveAdvantage(
                signal="Stakeholder communication",
                evidence_refs=["strength-e1", "strength-e2"],
                source_refs=["job:1", "job:2"],
                evidence_count=2,
                affected_role_families=["Product Operations"],
                direction_relevance="aligned" if target else "unknown",
                confidence="medium",
            )
        ] if sample_size else [],
        recurring_blockers=list(blockers),
        direction_alignment=DirectionAlignment(
            competitive_now=["Customer Support"],
            bridge=["Product Operations"],
            target=list(target),
            direction_known=bool(target),
            alignment_state=(
                "no_competitive_overlap_observed"
                if target
                else "direction_unknown"
            ),
        ),
        improvement_priorities=list(priorities),
        checkpoint_summary="Deterministic checkpoint.",
    )


def test_current_position_keeps_competitive_and_target_separate():
    view = build_career_intelligence_view(_snapshot())

    assert view["current_position"]["competitive_now"] == ["Customer Support"]
    assert view["current_position"]["target"] == ["Product Operations"]
    assert "Customer Support" not in view["current_position"]["target"]


def test_no_objective_never_invents_target_direction():
    view = build_career_intelligence_view(_snapshot(target=()))

    assert view["direction_known"] is False
    assert view["current_position"]["target"] == []
    assert view["current_position"]["competitive_now"] == ["Customer Support"]


def test_aligned_now_priority_appears_under_now():
    view = build_career_intelligence_view(
        _snapshot(priorities=[_priority("Create SQL project evidence")])
    )

    assert [item["title"] for item in view["priorities"]["now"]] == [
        "Create SQL project evidence"
    ]


def test_unrelated_item_is_not_rendered_as_now_recommendation():
    view = build_career_intelligence_view(
        _snapshot(
            priorities=[
                _priority(
                    "Create support portfolio",
                    band="now",
                    relevance="unrelated",
                )
            ]
        )
    )

    assert view["priorities"]["now"] == []
    assert view["priorities"]["watch"][0]["direction_relevance"] == "unrelated"


def test_structural_distance_is_separate_from_quick_actions():
    structural = RecurringBlocker(
        blocker="5 years enterprise ownership",
        gap_type="structural_distance",
        evidence_refs=["e1"],
        source_refs=["job:1"],
        evidence_count=1,
        affected_role_families=["Product Operations"],
        direction_relevance="aligned",
        confidence="low",
    )
    view = build_career_intelligence_view(_snapshot(blockers=[structural]))

    assert view["blockers"] == []
    assert view["structural_distances"][0]["blocker"] == (
        "5 years enterprise ownership"
    )
    assert view["priorities"]["now"] == []


def test_empty_history_and_plan_render_as_safe_view_state():
    view = build_career_intelligence_view(_snapshot(sample_size=0, priorities=[]))

    assert view["current_position"]["sample_size"] == 0
    assert view["current_position"]["average_fit_label"] == "Not available"
    assert view["advantages"] == []
    assert view["priorities"] == {"now": [], "next": [], "watch": []}


def test_confidence_semantics_and_support_are_preserved():
    view = build_career_intelligence_view(_snapshot())
    advantage = view["advantages"][0]

    assert advantage["confidence"] == "medium"
    assert advantage["confidence_label"] == "Medium confidence"
    assert advantage["evidence_count"] == 2
    assert "does not mean certainty" in CONFIDENCE_EXPLANATION


def test_snapshot_loader_builds_once_for_active_candidate():
    class SpyService:
        def __init__(self):
            self.calls = []

        def build(self, candidate_id):
            self.calls.append(candidate_id)
            return _snapshot()

    service = SpyService()
    snapshot = load_career_intelligence_snapshot(
        "candidate-a",
        snapshot_service=service,
    )

    assert snapshot.candidate_id == "candidate-a"
    assert service.calls == ["candidate-a"]
