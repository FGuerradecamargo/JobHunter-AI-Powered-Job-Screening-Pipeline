from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime
import hashlib
import json

from models.market_profile import (
    MarketConfidence,
    MarketJobObservation,
    MarketPattern,
    MarketProfile,
    MarketSegment,
)


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _matches(value: str, expected: str) -> bool:
    return not expected or _norm(value) == _norm(expected)


def _in_segment(
    observation: MarketJobObservation,
    segment: MarketSegment,
) -> bool:
    return (
        _matches(observation.role_family, segment.role_family)
        and _matches(observation.location, segment.location)
        and _matches(observation.seniority, segment.seniority)
        and _matches(observation.domain, segment.domain)
    )


def _confidence(
    independent_jobs: int,
    sample_size: int,
) -> MarketConfidence:
    # Conservative evidence confidence; not a product score.
    if independent_jobs >= 5 and sample_size >= 8:
        return MarketConfidence.HIGH
    if independent_jobs >= 2 and sample_size >= 3:
        return MarketConfidence.MEDIUM
    return MarketConfidence.LOW


def _source_signature(
    observations: list[MarketJobObservation],
    segment: MarketSegment,
) -> str:
    payload = {
        "segment": {
            "role_family": segment.role_family,
            "location": segment.location,
            "seniority": segment.seniority,
            "domain": segment.domain,
            "time_window": segment.time_window,
        },
        "observations": [
            {
                "job_id": item.job_id,
                "observed_at": item.observed_at,
                "source_refs": item.source_refs,
                "role_family": item.role_family,
                "location": item.location,
                "seniority": item.seniority,
                "domain": item.domain,
                "work_mode": item.work_mode,
                "employment_type": item.employment_type,
                "capabilities": item.capabilities,
                "tools": item.tools,
                "compensation_known": item.compensation_known,
                "compensation": item.compensation,
            }
            for item in sorted(
                observations,
                key=lambda item: json.dumps(asdict(item), sort_keys=True),
            )
        ],
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def build_market_profile(
    *,
    observations: list[MarketJobObservation],
    segment: MarketSegment,
    created_at: str,
    previous: MarketProfile | None = None,
) -> MarketProfile:
    now = datetime.fromisoformat(created_at)
    if now.tzinfo is None:
        raise ValueError("Market creation time requires a timezone.")
    if previous is not None and previous.segment != segment:
        raise ValueError("Market history must belong to the same segment.")
    start, end = None, now
    if segment.time_window:
        # Explicit inclusive UTC-compatible interval, never an ignored label.
        parts = segment.time_window.split("/")
        if len(parts) != 2:
            raise ValueError("Market time window must be start/end ISO timestamps.")
        start, end = map(datetime.fromisoformat, parts)
        if start.tzinfo is None or end.tzinfo is None or start > end or end > now:
            raise ValueError("Invalid market time window.")
    evidence = [item for item in observations
                if datetime.fromisoformat(item.observed_at) <= end
                and (start is None or datetime.fromisoformat(item.observed_at) >= start)]
    # Keep all source evidence in the signature; input order cannot set authority.
    evidence = list({json.dumps(asdict(item), sort_keys=True): item for item in evidence}.values())
    by_job = defaultdict(list)
    for item in evidence:
        by_job[item.job_id].append(item)
    selected = []
    uncertainties = set()
    for job_id, rows in sorted(by_job.items()):
        values = {}
        for name in ("role_family", "location", "seniority", "domain", "work_mode", "employment_type", "compensation"):
            known = {getattr(row, name) for row in rows if getattr(row, name)}
            normalized = {_norm(value) for value in known}
            values[name] = min(known) if len(normalized) == 1 else ""
            if len(normalized) > 1:
                uncertainties.add("conflicting_public_" + name)
        merged = replace(rows[0], **values,
                         compensation_known=bool(values["compensation"]),
                         source_refs=tuple(sorted({ref for row in rows for ref in row.source_refs})),
                         capabilities=tuple(sorted({v for row in rows for v in row.capabilities})),
                         tools=tuple(sorted({v for row in rows for v in row.tools})))
        if _in_segment(merged, segment):
            selected.append(merged)
    selected_ids = {item.job_id for item in selected}

    buckets = {
        "role_family": defaultdict(set),
        "seniority": defaultdict(set),
        "domain": defaultdict(set),
        "work_mode": defaultdict(set),
        "employment_type": defaultdict(set),
        "capability": defaultdict(set),
        "tool": defaultdict(set),
    }

    for item in selected:
        scalar = {
            "role_family": item.role_family,
            "seniority": item.seniority,
            "domain": item.domain,
            "work_mode": item.work_mode,
            "employment_type": item.employment_type,
        }
        for dimension, value in scalar.items():
            value = " ".join(str(value or "").split())
            if value:
                buckets[dimension][value].add(item.job_id)

        for value in item.capabilities:
            buckets["capability"][value].add(item.job_id)
        for value in item.tools:
            buckets["tool"][value].add(item.job_id)

    sample_size = len(selected)
    patterns = []
    for dimension, values in buckets.items():
        for label, job_ids in values.items():
            count = len(job_ids)
            patterns.append(
                MarketPattern(
                    dimension=dimension,
                    label=label,
                    independent_jobs=count,
                    sample_size=sample_size,
                    source_job_ids=tuple(sorted(job_ids)),
                    frequency=round(
                        count / sample_size,
                        4,
                    ) if sample_size else 0.0,
                    confidence=_confidence(
                        count,
                        sample_size,
                    ),
                )
            )

    patterns.sort(
        key=lambda item: (
            item.dimension,
            -item.independent_jobs,
            item.label.casefold(),
        )
    )

    signature = _source_signature(
        [item for item in evidence if item.job_id in selected_ids],
        segment,
    )
    if previous is not None and previous.source_signature == signature:
        return previous

    return MarketProfile(
        profile_version=(
            previous.profile_version + 1
            if previous
            else 1
        ),
        supersedes_version=(
            previous.profile_version
            if previous
            else None
        ),
        source_signature=signature,
        created_at=created_at,
        segment=segment,
        sample_size=sample_size,
        patterns=tuple(patterns),
        uncertainties=tuple(sorted(uncertainties | ({"small_sample"} if sample_size < 8 else set())
                                   | ({"no_observations"} if not sample_size else set()))),
        compensation_observed_count=sum(
            item.compensation_known
            for item in selected
        ),
    )
