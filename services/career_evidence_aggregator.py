from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from models.career_evidence import CareerEvidence
from models.career_evidence_signal import (
    CareerEvidenceSignal,
)


COMPETITIVE_RECOMMENDATIONS = {
    "best_match",
    "potential",
    "good_opportunity",
}

NEAR_MATCH_MIN_FIT = 50

COMPETITIVE_SIGNAL_TYPES = {
    "role_family",
    "market_strength",
}

NEAR_MARKET_SIGNAL_TYPES = {
    "best_match_blocker",
    "raise_fit",
}


def _normalize(
    value: str,
) -> str:
    value = re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    )

    value = re.sub(
        r"[.;:,]+$",
        "",
        value,
    )

    return value


def _signal_id(
    signal_type: str,
    statement: str,
) -> str:
    canonical = (
        f"{_normalize(signal_type).casefold()}|"
        f"{_normalize(statement).casefold()}"
    )

    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    return f"signal_{digest}"


def _is_competitive_metadata(
    metadata: dict,
) -> bool:
    recommendation = str(
        metadata.get(
            "recommendation",
            "",
        )
        or ""
    ).strip()

    return (
        recommendation
        in COMPETITIVE_RECOMMENDATIONS
    )


def _is_near_market_metadata(
    metadata: dict,
) -> bool:
    if _is_competitive_metadata(
        metadata
    ):
        return True

    fit = metadata.get(
        "current_fit"
    )

    return (
        isinstance(fit, int)
        and not isinstance(fit, bool)
        and fit >= NEAR_MATCH_MIN_FIT
    )


def confidence_from_observations(
    *,
    independent_sources: int,
    sample_size: int,
) -> str:
    if (
        independent_sources <= 0
        or sample_size <= 0
    ):
        return "low"

    frequency = (
        independent_sources
        / sample_size
    )

    if (
        independent_sources >= 4
        and frequency >= 0.50
    ):
        return "high"

    if (
        independent_sources >= 2
        and frequency >= 0.25
    ):
        return "medium"

    return "low"


def _eligible_sources_by_type(
    records: list[CareerEvidence],
) -> dict[str, set[str]]:
    competitive_sources: set[str] = set()
    near_market_sources: set[str] = set()
    all_market_sources: set[str] = set()

    source_metadata: dict[
        str,
        dict,
    ] = {}

    for record in records:
        if (
            record.evidence_type
            != "market_signal"
        ):
            continue

        source_ref = str(
            record.source_ref or ""
        ).strip()

        if not source_ref:
            continue

        all_market_sources.add(
            source_ref
        )

        source_metadata.setdefault(
            source_ref,
            record.metadata or {},
        )

    for (
        source_ref,
        metadata,
    ) in source_metadata.items():
        if _is_competitive_metadata(
            metadata
        ):
            competitive_sources.add(
                source_ref
            )

        if _is_near_market_metadata(
            metadata
        ):
            near_market_sources.add(
                source_ref
            )

    return {
        "competitive": competitive_sources,
        "near_market": near_market_sources,
        "all_market": all_market_sources,
    }


def _sample_sources_for_signal(
    *,
    signal_type: str,
    eligible_sources: dict[
        str,
        set[str],
    ],
) -> set[str]:
    if (
        signal_type
        in COMPETITIVE_SIGNAL_TYPES
    ):
        return eligible_sources[
            "competitive"
        ]

    if (
        signal_type
        in NEAR_MARKET_SIGNAL_TYPES
    ):
        return eligible_sources[
            "near_market"
        ]

    return eligible_sources[
        "all_market"
    ]


def aggregate_market_evidence(
    records: list[CareerEvidence],
) -> list[CareerEvidenceSignal]:
    market_records = [
        record
        for record in records
        if (
            record.evidence_type
            == "market_signal"
            and _normalize(
                record.statement
            )
        )
    ]

    eligible_sources = (
        _eligible_sources_by_type(
            market_records
        )
    )

    grouped: dict[
        tuple[str, str],
        list[CareerEvidence],
    ] = defaultdict(list)

    labels: dict[
        tuple[str, str],
        str,
    ] = {}

    for record in market_records:
        signal_type = _normalize(
            record.signal_type
        )

        statement = _normalize(
            record.statement
        )

        key = (
            signal_type.casefold(),
            statement.casefold(),
        )

        grouped[key].append(
            record
        )

        labels.setdefault(
            key,
            statement,
        )

    signals: list[
        CareerEvidenceSignal
    ] = []

    for (
        key,
        items,
    ) in grouped.items():
        signal_type = items[
            0
        ].signal_type

        statement = labels[key]

        evidence_refs = sorted(
            {
                item.evidence_id
                for item in items
            }
        )

        source_refs = sorted(
            {
                item.source_ref
                for item in items
                if item.source_ref
            }
        )

        role_families = sorted(
            {
                _normalize(
                    item.role_family
                )
                for item in items
                if _normalize(
                    item.role_family
                )
            },
            key=str.casefold,
        )

        sample_sources = (
            _sample_sources_for_signal(
                signal_type=signal_type,
                eligible_sources=(
                    eligible_sources
                ),
            )
        )

        independent_sources = len(
            source_refs
        )

        sample_size = len(
            sample_sources
        )

        frequency = (
            independent_sources
            / sample_size
            if sample_size
            else 0.0
        )

        signals.append(
            CareerEvidenceSignal(
                signal_id=_signal_id(
                    signal_type,
                    statement,
                ),
                signal_type=signal_type,
                statement=statement,
                evidence_refs=(
                    evidence_refs
                ),
                source_refs=(
                    source_refs
                ),
                role_families=(
                    role_families
                ),
                evidence_count=len(
                    evidence_refs
                ),
                independent_sources=(
                    independent_sources
                ),
                sample_size=(
                    sample_size
                ),
                frequency=round(
                    frequency,
                    4,
                ),
                confidence=confidence_from_observations(
                    independent_sources=(
                        independent_sources
                    ),
                    sample_size=(
                        sample_size
                    ),
                ),
            )
        )

    return sorted(
        signals,
        key=lambda item: (
            item.signal_type,
            -item.independent_sources,
            item.statement.casefold(),
        ),
    )
