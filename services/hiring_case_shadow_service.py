"""Opt-in local shadow execution after legacy analysis; no repositories or clients."""

from collections import Counter
from dataclasses import asdict
import json
import logging
from typing import Iterable

from models.hiring_case import (
    HIRING_CASE_SCHEMA_VERSION,
    RequirementEvidenceState,
    RequirementImportance,
)
from models.hiring_case_shadow import (
    HiringCaseShadowComparison,
    HiringCaseShadowSource,
    LegacyHiringClassification,
    ShadowComparisonState,
)
from services.hiring_case_compatibility import read_legacy_classification
from services.hiring_case_engine import build_hiring_case
from services.hiring_case_input_adapter import build_hiring_case_input, ShadowInputUnavailable


def _legacy_value(source: HiringCaseShadowSource) -> LegacyHiringClassification:
    raw = source.analysis_source.recommendation
    if not raw and isinstance(source.analysis_source.analysis, dict):
        raw = source.analysis_source.analysis.get("bucket", "")
    normalized = raw.strip().casefold() if isinstance(raw, str) else ""
    try:
        return LegacyHiringClassification(normalized)
    except ValueError:
        return LegacyHiringClassification.UNKNOWN


def evaluate_hiring_case_shadow(source: HiringCaseShadowSource) -> HiringCaseShadowComparison:
    legacy = _legacy_value(source)
    try:
        data = build_hiring_case_input(source)
    except ShadowInputUnavailable as error:
        result = HiringCaseShadowComparison(
            legacy_value=legacy, shadow_classification=None,
            comparison=ShadowComparisonState.NOT_EVALUATED,
            hiring_case_strength=None, opportunity_value=None,
            opportunity_confidence=None, unavailable_reason=error.reason,
        )
    else:
        case = build_hiring_case(data)
        mapped = read_legacy_classification(legacy.value).display_classification
        state = ShadowComparisonState.UNMAPPED
        if mapped is not None:
            state = (
                ShadowComparisonState.SAME if mapped is case.classification
                else ShadowComparisonState.DIFFERENT
            )
        counts = Counter(item.evidence_state for item in case.requirements)
        result = HiringCaseShadowComparison(
            legacy_value=legacy, shadow_classification=case.classification,
            comparison=state, hiring_case_strength=case.hiring_case_strength,
            opportunity_value=case.opportunity.value,
            opportunity_confidence=case.opportunity.confidence,
            proven_count=counts[RequirementEvidenceState.PROVEN],
            transferable_count=counts[RequirementEvidenceState.TRANSFERABLE],
            evidence_missing_count=counts[RequirementEvidenceState.EVIDENCE_MISSING],
            gap_count=counts[RequirementEvidenceState.GAP],
            core_gap_count=sum(
                item.importance is RequirementImportance.CORE
                and item.evidence_state is RequirementEvidenceState.GAP
                for item in case.requirements
            ),
            needs_evidence_count=sum(item.needs_evidence for item in case.how_to_prove.items),
        )
    # This object is built here from enums/counts only; never serialize the source/case.
    logging.getLogger(__name__).info(
        "%s", json.dumps({"event": "hiring_case_shadow", **asdict(result)}, sort_keys=True)
    )
    return result


def compare_hiring_case_fixtures(sources: Iterable[HiringCaseShadowSource]) -> dict:
    """Content-free aggregate harness. Unmapped and unevaluable rows stay explicit."""
    results = [evaluate_hiring_case_shadow(source) for source in sources]
    evaluated = [item for item in results if item.shadow_classification is not None]
    states = Counter(item.comparison for item in results)
    transitions = Counter(
        f"{item.legacy_value.value} -> {item.shadow_classification.value}"
        for item in evaluated
    )
    missing = sum(item.evidence_missing_count for item in evaluated)
    gaps = sum(item.core_gap_count for item in evaluated)
    return {
        "schema_version": HIRING_CASE_SCHEMA_VERSION,
        "comparison_schema_version": "hiring-case-shadow-v1",
        "authoritative": False,
        "total": len(results),
        "evaluated": len(evaluated),
        "same": states[ShadowComparisonState.SAME],
        "changed": states[ShadowComparisonState.DIFFERENT],
        "unmapped": states[ShadowComparisonState.UNMAPPED],
        "not_evaluated": states[ShadowComparisonState.NOT_EVALUATED],
        "transitions": dict(sorted(transitions.items())),
        "evidence_missing_total": missing,
        "evidence_missing_average": missing / len(evaluated) if evaluated else 0.0,
        "core_gap_total": gaps,
        "core_gap_average": gaps / len(evaluated) if evaluated else 0.0,
    }
