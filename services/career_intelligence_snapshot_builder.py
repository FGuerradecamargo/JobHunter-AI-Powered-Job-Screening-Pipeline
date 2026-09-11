from __future__ import annotations

from dataclasses import asdict
import re

from models.career_evidence import CareerEvidence
from models.career_intelligence_snapshot import (
    CareerIntelligenceSnapshot,
    CompetitiveAdvantage,
    DirectionAlignment,
)
from models.career_objective import CareerObjective
from models.current_market_position import CurrentMarketPosition
from models.gap_and_leverage import GapAndLeverageAssessment
from models.improvement_plan import ImprovementPlan
from services.career_memory_source_builder import build_source_signature
from services.role_family_normalizer import normalize_role_family


CAREER_INTELLIGENCE_SCHEMA_VERSION = "career-intelligence-v1"


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _sorted_labels(values) -> list[str]:
    labels = {}
    for value in values or []:
        label = normalize_role_family(value)
        if label:
            labels.setdefault(label.casefold(), label)
    return sorted(labels.values(), key=str.casefold)


def _source_payload(
    records: list[CareerEvidence],
    objective: CareerObjective | None,
) -> dict:
    evidence = [asdict(record) for record in records or []]
    evidence.sort(key=build_source_signature)

    objective_payload = {}
    if objective is not None:
        objective_payload = {
            "id": _normalize(objective.id),
            "title": _normalize(objective.title),
            "description": _normalize(objective.description),
            "active": bool(objective.active),
            "desired_role_families": _sorted_labels(
                objective.desired_role_families
            ),
        }

    return {
        "career_evidence": evidence,
        "career_objective": objective_payload,
    }


def _direction_alignment(
    position: CurrentMarketPosition,
    assessment: GapAndLeverageAssessment,
) -> DirectionAlignment:
    competitive = _sorted_labels(
        item.role_family for item in position.competitive_role_families
    )
    bridge = _sorted_labels(
        item.role_family for item in position.bridge_role_families
    )
    target = _sorted_labels(
        item.role_family for item in position.target_role_families
    )
    competitive_keys = {item.casefold() for item in competitive}
    overlap = [item for item in target if item.casefold() in competitive_keys]
    distances = _sorted_labels(
        item.blocker
        for item in assessment.recurring_blockers
        if item.gap_type in {"distance_signal", "structural_distance"}
    )

    if not target:
        alignment_state = "direction_unknown"
    elif overlap:
        alignment_state = "competitive_overlap_observed"
    else:
        alignment_state = "no_competitive_overlap_observed"

    return DirectionAlignment(
        competitive_now=competitive,
        bridge=bridge,
        target=target,
        competitive_target_overlap=overlap,
        distance_signals=distances,
        direction_known=bool(target),
        alignment_state=alignment_state,
    )


def build_career_intelligence_snapshot(
    *,
    candidate_id: str,
    generated_at: str,
    evidence_records: list[CareerEvidence],
    objective: CareerObjective | None,
    current_market_position: CurrentMarketPosition,
    gap_and_leverage: GapAndLeverageAssessment,
    improvement_plan: ImprovementPlan,
) -> CareerIntelligenceSnapshot:
    normalized_candidate_id = _normalize(candidate_id)
    if not normalized_candidate_id:
        raise ValueError("candidate_id must be non-empty.")

    for owner, value in (
        ("Current market position", current_market_position.candidate_id),
        ("Gap and leverage assessment", gap_and_leverage.candidate_id),
        ("Improvement plan", improvement_plan.candidate_id),
    ):
        if value != normalized_candidate_id:
            raise PermissionError(f"{owner} belongs to another candidate.")
    if objective is not None and objective.candidate_id != normalized_candidate_id:
        raise PermissionError("Career objective belongs to another candidate.")

    alignment = _direction_alignment(current_market_position, gap_and_leverage)
    advantages = [
        CompetitiveAdvantage(
            signal=item.strength,
            evidence_refs=list(item.evidence_refs),
            source_refs=list(item.source_refs),
            evidence_count=len(set(item.evidence_refs)),
            affected_role_families=list(item.affected_role_families),
            direction_relevance=item.direction_relevance,
            confidence=item.confidence,
        )
        for item in gap_and_leverage.market_strengths
        if item.evidence_refs and item.source_refs
    ]
    advantages.sort(key=lambda item: (item.signal.casefold(), item.evidence_refs))

    summary = (
        f"{len(alignment.competitive_now)} competitive role families observed; "
        f"{len(alignment.target)} explicit target role families; "
        f"{len(improvement_plan.priorities)} improvement priorities."
    )

    return CareerIntelligenceSnapshot(
        candidate_id=normalized_candidate_id,
        objective_id=_normalize(objective.id) if objective is not None else "",
        schema_version=CAREER_INTELLIGENCE_SCHEMA_VERSION,
        generated_at=_normalize(generated_at),
        source_signature=build_source_signature(
            _source_payload(evidence_records, objective)
        ),
        current_market_position=current_market_position,
        competitive_advantages=advantages,
        recurring_blockers=list(gap_and_leverage.recurring_blockers),
        leverage_opportunities=list(gap_and_leverage.leverage_opportunities),
        direction_alignment=alignment,
        improvement_priorities=list(improvement_plan.priorities),
        checkpoint_summary=summary,
    )
