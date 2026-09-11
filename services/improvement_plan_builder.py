from __future__ import annotations

import hashlib
import re

from models.gap_and_leverage import GapAndLeverageAssessment
from models.improvement_plan import ImprovementPlan, ImprovementPriority


_BAND_RANK = {"now": 0, "next": 1, "watch": 2}
_DIRECTION_RANK = {"aligned": 0, "unknown": 1, "unrelated": 2}
_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _priority_id(category: str, title: str) -> str:
    canonical = f"{category.casefold()}|{title.casefold()}"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"priority_{digest}"


def _priority(
    *,
    title: str,
    category: str,
    why_now: str,
    related_objective: str,
    direction_relevance: str,
    affected_role_families: list[str],
    evidence_refs: list[str],
    source_refs: list[str],
    confidence: str,
    priority_band: str,
) -> ImprovementPriority:
    return ImprovementPriority(
        priority_id=_priority_id(category, title),
        title=title,
        category=category,
        why_now=why_now,
        related_objective=related_objective,
        direction_relevance=direction_relevance,
        affected_role_families=list(affected_role_families),
        evidence_refs=list(evidence_refs),
        source_refs=list(source_refs),
        confidence=confidence,
        priority_band=priority_band,
    )


def _leverage_band(direction: str, confidence: str) -> str:
    if direction == "aligned" and confidence == "high":
        return "now"
    if direction == "aligned" and confidence == "medium":
        return "next"
    return "watch"


def _sort_key(item: ImprovementPriority) -> tuple:
    return (
        _BAND_RANK[item.priority_band],
        _DIRECTION_RANK[item.direction_relevance],
        _CONFIDENCE_RANK[item.confidence],
        -len(item.affected_role_families),
        -len(item.source_refs),
        item.priority_id,
    )


def build_improvement_plan(
    *,
    candidate_id: str,
    assessment: GapAndLeverageAssessment,
    related_objective: str = "",
) -> ImprovementPlan:
    normalized_candidate_id = _normalize(candidate_id)
    if not normalized_candidate_id:
        raise ValueError("candidate_id must be non-empty.")
    if assessment.candidate_id != normalized_candidate_id:
        raise PermissionError("Gap and leverage assessment belongs to another candidate.")

    objective = _normalize(related_objective) if assessment.direction_known else ""
    priorities = []

    for item in assessment.leverage_opportunities:
        band = _leverage_band(item.direction_relevance, item.confidence)
        if item.direction_relevance == "unknown":
            category = "exploration"
            title = f"Explore whether this move fits your direction: {item.action}"
            why_now = (
                "Repeated market evidence suggests possible leverage, but no "
                "explicit career direction confirms it should be pursued."
            )
        else:
            category = (
                "evidence"
                if item.leverage_type == "evidence_development"
                else "capability"
            )
            title = item.action
            why_now = item.rationale

        priorities.append(
            _priority(
                title=title,
                category=category,
                why_now=why_now,
                related_objective=(
                    objective if item.direction_relevance == "aligned" else ""
                ),
                direction_relevance=item.direction_relevance,
                affected_role_families=item.affected_role_families,
                evidence_refs=item.evidence_refs,
                source_refs=item.source_refs,
                confidence=item.confidence,
                priority_band=band,
            )
        )

    for item in assessment.recurring_blockers:
        if item.gap_type != "structural_distance":
            continue
        priorities.append(
            _priority(
                title=f"Monitor structural distance: {item.blocker}",
                category="exploration",
                why_now=(
                    "Observed structural distance is not a credible short-term "
                    "development action."
                ),
                related_objective=(
                    objective if item.direction_relevance == "aligned" else ""
                ),
                direction_relevance=item.direction_relevance,
                affected_role_families=item.affected_role_families,
                evidence_refs=item.evidence_refs,
                source_refs=item.source_refs,
                confidence=item.confidence,
                priority_band="watch",
            )
        )

    for item in assessment.market_strengths:
        if not (
            item.direction_relevance == "aligned"
            and item.confidence == "high"
            and len(item.source_refs) >= 2
        ):
            continue
        priorities.append(
            _priority(
                title=f"Keep demonstrating: {item.strength}",
                category="evidence",
                why_now=(
                    "This recurring strength already supports competitiveness "
                    "across the chosen direction."
                ),
                related_objective=objective,
                direction_relevance="aligned",
                affected_role_families=item.affected_role_families,
                evidence_refs=item.evidence_refs,
                source_refs=item.source_refs,
                confidence=item.confidence,
                priority_band="next",
            )
        )

    return ImprovementPlan(
        candidate_id=normalized_candidate_id,
        priorities=sorted(priorities, key=_sort_key),
        related_objective=objective,
        target_role_families=list(assessment.target_role_families),
        direction_known=assessment.direction_known,
    )

