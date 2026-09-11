from __future__ import annotations

import re

from models.career_evidence_signal import CareerEvidenceSignal
from models.current_market_position import CurrentMarketPosition
from models.gap_and_leverage import (
    GapAndLeverageAssessment,
    LeverageOpportunity,
    MarketLeverageStrength,
    RecurringBlocker,
)


_ACTION_MARKERS = (
    "build ",
    "complete ",
    "create ",
    "demonstrate ",
    "document ",
    "earn ",
    "obtain ",
    "publish ",
    "showcase ",
)

_ACTION_NOUNS = (
    "certification",
    "credential",
    "portfolio",
    "project evidence",
)

_STRUCTURAL_PATTERNS = (
    re.compile(r"\b\d+\s*\+?\s*years?\b", re.IGNORECASE),
    re.compile(r"\bdirect\b.*\bexperience\b", re.IGNORECASE),
    re.compile(r"\bproduction\b.*\bexperience\b", re.IGNORECASE),
    re.compile(r"\benterprise\b.*\bexperience\b", re.IGNORECASE),
    re.compile(r"\bsenior(?:-level)?\b.*\bexperience\b", re.IGNORECASE),
)


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _labels(values) -> dict[str, str]:
    result = {}
    for value in values or []:
        label = _normalize(value)
        if label:
            result.setdefault(label.casefold(), label)
    return result


def _direction_relevance(
    role_families: list[str],
    target_keys: set[str],
) -> str:
    if not target_keys:
        return "unknown"
    role_keys = {_normalize(item).casefold() for item in role_families}
    return "aligned" if role_keys & target_keys else "unrelated"


def _is_actionable_raise_fit(statement: str) -> bool:
    normalized = _normalize(statement)
    lowered = normalized.casefold()
    if _is_structural_raise_fit(normalized):
        return False
    return lowered.startswith(_ACTION_MARKERS) or any(
        noun in lowered for noun in _ACTION_NOUNS
    )


def _is_structural_raise_fit(statement: str) -> bool:
    return any(pattern.search(statement) for pattern in _STRUCTURAL_PATTERNS)


def _sort_key(item) -> tuple:
    relevance_rank = {"aligned": 0, "unknown": 1, "unrelated": 2}
    sources = len(item.source_refs)
    label = getattr(item, "blocker", None) or getattr(
        item, "action", None
    ) or item.strength
    return (relevance_rank[item.direction_relevance], -sources, label.casefold())


def build_gap_and_leverage_assessment(
    *,
    candidate_id: str,
    market_signals: list[CareerEvidenceSignal],
    current_market_position: CurrentMarketPosition,
) -> GapAndLeverageAssessment:
    normalized_candidate_id = _normalize(candidate_id)
    if not normalized_candidate_id:
        raise ValueError("candidate_id must be non-empty.")
    if current_market_position.candidate_id != normalized_candidate_id:
        raise PermissionError("Current market position belongs to another candidate.")

    target_labels = _labels(
        item.role_family
        for item in current_market_position.target_role_families
    )
    target_keys = set(target_labels)
    blockers = []
    leverage = []
    strengths = []

    for signal in market_signals or []:
        relevance = _direction_relevance(signal.role_families, target_keys)
        common = {
            "evidence_refs": list(signal.evidence_refs),
            "source_refs": list(signal.source_refs),
            "affected_role_families": list(signal.role_families),
            "direction_relevance": relevance,
            "confidence": signal.confidence,
        }

        if signal.signal_type == "best_match_blocker":
            blockers.append(
                RecurringBlocker(
                    blocker=signal.statement,
                    evidence_count=signal.evidence_count,
                    independent_sources=signal.independent_sources,
                    **common,
                )
            )
        elif (
            signal.signal_type == "raise_fit"
            and not _is_actionable_raise_fit(signal.statement)
        ):
            blockers.append(
                RecurringBlocker(
                    blocker=signal.statement,
                    gap_type=(
                        "structural_distance"
                        if _is_structural_raise_fit(signal.statement)
                        else "distance_signal"
                    ),
                    evidence_count=signal.evidence_count,
                    independent_sources=signal.independent_sources,
                    **common,
                )
            )
        elif signal.signal_type == "market_strength":
            strengths.append(
                MarketLeverageStrength(strength=signal.statement, **common)
            )
        elif (
            signal.signal_type == "raise_fit"
            and signal.independent_sources >= 2
            and _is_actionable_raise_fit(signal.statement)
        ):
            impact = (
                "multiple_direction_aligned_opportunities"
                if relevance == "aligned"
                else "multiple_observed_opportunities"
            )
            leverage.append(
                LeverageOpportunity(
                    action=signal.statement,
                    rationale=(
                        "Repeated raise-fit evidence across independent "
                        "market opportunities."
                    ),
                    expected_best_match_impact=impact,
                    **common,
                )
            )

    return GapAndLeverageAssessment(
        candidate_id=normalized_candidate_id,
        recurring_blockers=sorted(blockers, key=_sort_key),
        leverage_opportunities=sorted(leverage, key=_sort_key),
        market_strengths=sorted(strengths, key=_sort_key),
        target_role_families=sorted(target_labels.values(), key=str.casefold),
        direction_known=bool(target_keys),
    )
