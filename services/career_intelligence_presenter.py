from models.career_intelligence_snapshot import CareerIntelligenceSnapshot
from services.career_intelligence_snapshot_service import CareerIntelligenceSnapshotService


CONFIDENCE_EXPLANATION = (
    "Confidence reflects how consistently a signal appears in the observed "
    "evidence. It does not mean certainty about your career."
)

_CONFIDENCE_LABELS = {
    "high": "High confidence",
    "medium": "Medium confidence",
    "low": "Early signal",
}

_DIRECTION_LABELS = {
    "aligned": "Aligned with your direction",
    "unrelated": "Outside your selected direction",
    "unknown": "Direction not selected",
}


def _confidence_label(value: str) -> str:
    return _CONFIDENCE_LABELS.get(value, "Early signal")


def _direction_label(value: str) -> str:
    return _DIRECTION_LABELS.get(value, "Direction not selected")


def _blocker_view(item) -> dict:
    return {
        "blocker": item.blocker,
        "role_families": list(item.affected_role_families),
        "direction_relevance": item.direction_relevance,
        "direction_label": _direction_label(item.direction_relevance),
        "confidence": item.confidence,
        "confidence_label": _confidence_label(item.confidence),
        "evidence_count": item.evidence_count,
        "source_count": len(item.source_refs),
    }


def _priority_view(item) -> dict:
    return {
        "title": item.title,
        "category": item.category,
        "category_label": item.category.replace("_", " ").title(),
        "why_now": item.why_now,
        "related_objective": item.related_objective,
        "direction_relevance": item.direction_relevance,
        "direction_label": _direction_label(item.direction_relevance),
        "confidence": item.confidence,
        "confidence_label": _confidence_label(item.confidence),
        "role_families": list(item.affected_role_families),
        "source_count": len(item.source_refs),
        "evidence_count": len(item.evidence_refs),
    }


def load_career_intelligence_snapshot(
    candidate_id: str,
    snapshot_service=None,
) -> CareerIntelligenceSnapshot:
    service = snapshot_service or CareerIntelligenceSnapshotService()
    return service.build(candidate_id)


def build_career_intelligence_view(
    snapshot: CareerIntelligenceSnapshot,
) -> dict:
    position = snapshot.current_market_position
    priorities = {"now": [], "next": [], "watch": []}

    for item in snapshot.improvement_priorities:
        band = item.priority_band if item.priority_band in priorities else "watch"
        if band == "now" and item.direction_relevance != "aligned":
            band = "watch"
        priorities[band].append(_priority_view(item))

    blockers = []
    structural_distances = []
    for item in snapshot.recurring_blockers:
        target = (
            structural_distances
            if item.gap_type == "structural_distance"
            else blockers
        )
        target.append(_blocker_view(item))

    advantages = [
        {
            "signal": item.signal,
            "evidence_count": item.evidence_count,
            "confidence": item.confidence,
            "confidence_label": _confidence_label(item.confidence),
            "role_families": list(item.affected_role_families),
        }
        for item in snapshot.competitive_advantages
    ]

    average_fit_label = (
        f"{position.average_fit:.1f}%"
        if position.average_fit is not None
        else "Not available"
    )

    return {
        "schema_version": snapshot.schema_version,
        "checkpoint_summary": snapshot.checkpoint_summary,
        "direction_known": snapshot.direction_alignment.direction_known,
        "current_position": {
            "sample_size": position.sample_size,
            "best_match_count": position.best_match_count,
            "near_match_count": position.near_match_count,
            "average_fit_label": average_fit_label,
            "competitive_now": list(snapshot.direction_alignment.competitive_now),
            "bridge": list(snapshot.direction_alignment.bridge),
            "target": list(snapshot.direction_alignment.target),
        },
        "advantages": advantages,
        "blockers": blockers,
        "structural_distances": structural_distances,
        "priorities": priorities,
        "priority_empty_messages": {
            "now": "There is not enough aligned evidence for a Now priority.",
            "next": "No follow-up priority is supported yet.",
            "watch": "There is nothing additional to watch right now.",
        },
    }
