from __future__ import annotations

import re
from collections import defaultdict

from models.career_evidence import CareerEvidence
from models.current_market_position import (
    CurrentMarketPosition,
    MarketPositionRoleFamily,
)
from services.career_evidence_aggregator import (
    COMPETITIVE_RECOMMENDATIONS,
    NEAR_MATCH_MIN_FIT,
    confidence_from_observations,
)


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _valid_fit(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 100 else None


def _unique_labels(values) -> dict[str, str]:
    labels = {}
    for value in values or []:
        label = _normalize(value)
        if label:
            labels.setdefault(label.casefold(), label)
    return labels


def _market_jobs(
    records: list[CareerEvidence],
) -> dict[str, dict]:
    jobs: dict[str, dict] = {}

    for record in records or []:
        if record.evidence_type != "market_signal":
            continue

        source_ref = _normalize(record.source_ref)
        if not source_ref:
            continue

        metadata = record.metadata or {}
        job = jobs.setdefault(
            source_ref,
            {
                "source_ref": source_ref,
                "recommendation": _normalize(
                    metadata.get("recommendation")
                ),
                "current_fit": _valid_fit(
                    metadata.get("current_fit")
                ),
                "roles": {},
            },
        )

        if record.signal_type == "role_family":
            role = _normalize(record.role_family or record.statement)
            if role:
                role_item = job["roles"].setdefault(
                    role.casefold(),
                    {"label": role, "evidence_refs": set()},
                )
                role_item["evidence_refs"].add(record.evidence_id)

    return jobs


def _role_conclusions(
    *,
    role_sources: dict[str, set[str]],
    role_evidence: dict[str, set[str]],
    labels: dict[str, str],
    sample_size: int,
    authority: str,
) -> list[MarketPositionRoleFamily]:
    conclusions = []

    for key, sources in role_sources.items():
        independent_sources = len(sources)
        conclusions.append(
            MarketPositionRoleFamily(
                role_family=labels[key],
                authority=authority,
                evidence_refs=sorted(role_evidence.get(key, set())),
                source_refs=sorted(sources),
                independent_sources=independent_sources,
                sample_size=sample_size,
                frequency=round(
                    independent_sources / sample_size,
                    4,
                ) if sample_size else 0.0,
                confidence=confidence_from_observations(
                    independent_sources=independent_sources,
                    sample_size=sample_size,
                ),
            )
        )

    return sorted(
        conclusions,
        key=lambda item: (
            -item.independent_sources,
            item.role_family.casefold(),
        ),
    )


def build_current_market_position(
    *,
    candidate_id: str,
    evidence_records: list[CareerEvidence],
    target_role_families: list[str] | None = None,
) -> CurrentMarketPosition:
    normalized_candidate_id = _normalize(candidate_id)
    if not normalized_candidate_id:
        raise ValueError("candidate_id must be non-empty.")

    jobs = _market_jobs(evidence_records)
    target_labels = _unique_labels(target_role_families)
    target_keys = set(target_labels)
    competitive_sources = defaultdict(set)
    competitive_evidence = defaultdict(set)
    bridge_sources = defaultdict(set)
    bridge_evidence = defaultdict(set)
    observed_sources = defaultdict(set)
    observed_evidence = defaultdict(set)
    observed_labels = {}
    viable_fits = []
    best_match_count = 0
    near_match_count = 0

    for source_ref, job in jobs.items():
        recommendation = job["recommendation"]
        fit = job["current_fit"]
        competitive = recommendation in COMPETITIVE_RECOMMENDATIONS
        near_market = competitive or (
            fit is not None and fit >= NEAR_MATCH_MIN_FIT
        )
        role_keys = set(job["roles"])
        aligned = bool(role_keys & target_keys)

        if near_market and fit is not None:
            viable_fits.append(fit)

        if aligned and recommendation == "best_match":
            best_match_count += 1
        elif aligned and near_market:
            near_match_count += 1

        for key, role in job["roles"].items():
            observed_labels.setdefault(key, role["label"])
            observed_sources[key].add(source_ref)
            observed_evidence[key].update(role["evidence_refs"])

            if competitive:
                competitive_sources[key].add(source_ref)
                competitive_evidence[key].update(role["evidence_refs"])
            elif near_market:
                bridge_sources[key].add(source_ref)
                bridge_evidence[key].update(role["evidence_refs"])

    for key in set(competitive_sources):
        bridge_sources.pop(key, None)
        bridge_evidence.pop(key, None)

    competitive = _role_conclusions(
        role_sources=competitive_sources,
        role_evidence=competitive_evidence,
        labels=observed_labels,
        sample_size=len(jobs),
        authority="market_evidence",
    )
    bridges = _role_conclusions(
        role_sources=bridge_sources,
        role_evidence=bridge_evidence,
        labels=observed_labels,
        sample_size=len(jobs),
        authority="market_evidence",
    )

    targets = []
    for key, label in sorted(
        target_labels.items(),
        key=lambda item: item[1].casefold(),
    ):
        sources = observed_sources.get(key, set())
        independent_sources = len(sources)
        targets.append(
            MarketPositionRoleFamily(
                role_family=label,
                authority="user_direction",
                evidence_refs=sorted(observed_evidence.get(key, set())),
                source_refs=sorted(sources),
                independent_sources=independent_sources,
                sample_size=len(jobs),
                frequency=round(
                    independent_sources / len(jobs),
                    4,
                ) if jobs else 0.0,
                confidence=confidence_from_observations(
                    independent_sources=independent_sources,
                    sample_size=len(jobs),
                ),
            )
        )

    return CurrentMarketPosition(
        candidate_id=normalized_candidate_id,
        competitive_role_families=competitive,
        bridge_role_families=bridges,
        target_role_families=targets,
        average_fit=(
            round(sum(viable_fits) / len(viable_fits), 1)
            if viable_fits else None
        ),
        fit_sample_size=len(viable_fits),
        best_match_count=best_match_count,
        near_match_count=near_match_count,
        sample_size=len(jobs),
    )
