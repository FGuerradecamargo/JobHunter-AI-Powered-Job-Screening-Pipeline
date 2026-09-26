from __future__ import annotations

import hashlib
from collections import defaultdict

from models.candidate_market import (
    CandidateImprovement,
    CandidateImprovementPlan,
    CandidateMarketAssessment,
    CandidateMarketSignal,
    CandidateMarketState,
    ImprovementBand,
    ImprovementKind,
)
from models.market_profile import MarketConfidence, MarketProfile
from models.profile_interpretation import CandidateProfileSnapshot
from services.role_family_normalizer import role_family_key


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _refs(values) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def build_candidate_market(
    *,
    candidate_profile: CandidateProfileSnapshot,
    market_profile: MarketProfile,
) -> CandidateMarketAssessment:
    capability_by_label = defaultdict(list)
    for item in candidate_profile.capabilities:
        capability_by_label[_norm(item.label)].append(item)
    confirmed_gaps = {
        _norm(item)
        for item in candidate_profile.confirmed_gaps
    }
    direction_known = bool(candidate_profile.objectives)
    # A known objective is not proof that this particular market is relevant.
    direction_aligned = bool(market_profile.segment.role_family) and role_family_key(
        market_profile.segment.role_family
    ) in {role_family_key(value) for value in candidate_profile.objectives}

    signals = []
    for pattern in market_profile.patterns:
        if pattern.dimension not in {"capability", "tool"}:
            continue

        key = _norm(pattern.label)
        capabilities = capability_by_label.get(key, ())

        if capabilities and key in confirmed_gaps:
            # Contradictory snapshot evidence needs resolution, not a BUILD order.
            state = CandidateMarketState.EVIDENCE_MISSING
            evidence_refs = ()
        elif capabilities:
            state = (
                CandidateMarketState.TRANSFERABLE
                if all(item.transferable for item in capabilities)
                else CandidateMarketState.PROVEN
            )
            evidence_refs = tuple(ref for item in capabilities for ref in item.evidence_refs)
        elif key in confirmed_gaps and candidate_profile.source_refs:
            state = CandidateMarketState.CONFIRMED_GAP
            evidence_refs = candidate_profile.source_refs
        else:
            state = CandidateMarketState.EVIDENCE_MISSING
            evidence_refs = ()

        signals.append(
            CandidateMarketSignal(
                dimension=pattern.dimension,
                label=pattern.label,
                state=state,
                market_confidence=pattern.confidence.value,
                frequency=pattern.frequency,
                source_job_ids=pattern.source_job_ids,
                candidate_evidence_refs=_refs(evidence_refs),
                direction_relevance=(
                    "aligned"
                    if direction_aligned
                    else "unknown"
                ),
            )
        )

    return CandidateMarketAssessment(
        candidate_id=candidate_profile.candidate_id,
        candidate_profile_version=candidate_profile.profile_version,
        market_profile_version=market_profile.profile_version,
        market_source_signature=market_profile.source_signature,
        signals=tuple(signals),
        direction_known=direction_known,
        candidate_memory_signature=candidate_profile.memory_signature,
        evidence_gap_labels=tuple(candidate_profile.evidence_gaps),
    )


def _band(signal: CandidateMarketSignal) -> ImprovementBand:
    if signal.direction_relevance != "aligned":
        return ImprovementBand.WATCH
    if (
        signal.market_confidence == MarketConfidence.HIGH.value
        and signal.frequency >= 0.5
    ):
        return ImprovementBand.NOW
    if signal.market_confidence in {
        MarketConfidence.HIGH.value,
        MarketConfidence.MEDIUM.value,
    }:
        return ImprovementBand.NEXT
    return ImprovementBand.WATCH


def _id(kind: ImprovementKind, label: str, dimension: str) -> str:
    digest = hashlib.sha256(
        f"{kind.value}|{dimension}|{_norm(label)}".encode("utf-8")
    ).hexdigest()
    return f"improvement_{digest}"


def build_improvement_plan(
    assessment: CandidateMarketAssessment,
    *,
    evidence_gap_labels: tuple[str, ...] | None = None,
) -> CandidateImprovementPlan:
    evidence_gaps = {_norm(item) for item in assessment.evidence_gap_labels}
    if evidence_gap_labels is not None and {_norm(item) for item in evidence_gap_labels} != evidence_gaps:
        raise ValueError("Evidence gaps must come from the assessed candidate snapshot.")
    improvements = []

    for signal in assessment.signals:
        if signal.state is CandidateMarketState.PROVEN:
            continue

        if signal.state is CandidateMarketState.CONFIRMED_GAP:
            kind = ImprovementKind.BUILD
            why = (
                "Your profile records a confirmed gap for this capability, "
                "which appears in the observed market sample."
            )
        elif signal.state is CandidateMarketState.TRANSFERABLE:
            kind = ImprovementKind.PROVE
            why = (
                "You have adjacent evidence. Stronger direct evidence could "
                "make this easier to demonstrate."
            )
        elif _norm(signal.label) in evidence_gaps:
            kind = ImprovementKind.PROVE
            why = (
                "Your profile marks this as an evidence gap and the market "
                "sample contains it."
            )
        else:
            kind = ImprovementKind.EXPLORE
            why = (
                "The market signal is real, but your current evidence does "
                "not establish whether this is something to build or simply "
                "something you already do but have not documented."
            )

        improvements.append(
            CandidateImprovement(
                improvement_id=_id(kind, signal.label, signal.dimension),
                label=signal.label,
                kind=kind,
                band=_band(signal),
                why=why,
                market_confidence=signal.market_confidence,
                frequency=signal.frequency,
                source_job_ids=signal.source_job_ids,
                candidate_evidence_refs=signal.candidate_evidence_refs,
            )
        )

    band_rank = {
        ImprovementBand.NOW: 0,
        ImprovementBand.NEXT: 1,
        ImprovementBand.WATCH: 2,
    }
    kind_rank = {
        ImprovementKind.BUILD: 0,
        ImprovementKind.PROVE: 1,
        ImprovementKind.EXPLORE: 2,
    }
    improvements.sort(
        key=lambda item: (
            band_rank[item.band],
            kind_rank[item.kind],
            -item.frequency,
            item.label.casefold(),
        )
    )

    return CandidateImprovementPlan(
        candidate_id=assessment.candidate_id,
        candidate_profile_version=assessment.candidate_profile_version,
        market_profile_version=assessment.market_profile_version,
        improvements=tuple(improvements),
        candidate_memory_signature=assessment.candidate_memory_signature,
        market_source_signature=assessment.market_source_signature,
    )
