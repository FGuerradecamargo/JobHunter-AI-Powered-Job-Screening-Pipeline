from typing import Any


BEST_MATCH = "best_match"
TRADEOFF = "tradeoff"
LOWER_ALIGNMENT = "lower_alignment"
REJECT = "reject"


def classify_job_bucket(
    analysis: dict[str, Any],
) -> str:
    competitive_status = analysis.get(
        "competitive_status",
        "",
    )

    direction_alignment = analysis.get(
        "direction_alignment",
        "",
    )

    hard_conflicts = analysis.get(
        "hard_conflicts",
        [],
    ) or []

    personal_negatives = analysis.get(
        "personal_negatives",
        [],
    ) or []

    priority_conflicts = analysis.get(
        "priority_conflicts",
        [],
    ) or []

    if hard_conflicts:
        return REJECT

    if competitive_status not in {
        "competitive_now",
        "bridge_opportunity",
    }:
        return REJECT

    has_tradeoff = bool(
        personal_negatives
        or priority_conflicts
    )

    if direction_alignment == "high":
        if has_tradeoff:
            return TRADEOFF

        return BEST_MATCH

    if direction_alignment in {
        "medium",
        "low",
    }:
        return LOWER_ALIGNMENT

    return REJECT
