import pytest

from models.career_evidence import CareerEvidence

from services.career_evidence_aggregator import (
    aggregate_market_evidence,
    confidence_from_observations,
)


def _record(
    *,
    evidence_id: str,
    job_id: str,
    signal_type: str,
    statement: str,
    recommendation: str,
    current_fit: int,
    role_family: str = (
        "Product Operations"
    ),
) -> CareerEvidence:
    return CareerEvidence(
        evidence_id=evidence_id,
        evidence_type="market_signal",
        signal_type=signal_type,
        source_ref=f"job:{job_id}",
        statement=statement,
        role_family=role_family,
        authority="market_evidence",
        metadata={
            "job_id": job_id,
            "recommendation": (
                recommendation
            ),
            "current_fit": current_fit,
        },
    )


def test_aggregates_repeated_signal_across_jobs():
    records = [
        _record(
            evidence_id="e1",
            job_id="1",
            signal_type=(
                "best_match_blocker"
            ),
            statement="SQL",
            recommendation="potential",
            current_fit=70,
        ),
        _record(
            evidence_id="e2",
            job_id="2",
            signal_type=(
                "best_match_blocker"
            ),
            statement="sql",
            recommendation=(
                "good_opportunity"
            ),
            current_fit=65,
        ),
    ]

    signals = aggregate_market_evidence(
        records
    )

    signal = signals[0]

    assert signal.statement == "SQL"
    assert signal.evidence_count == 2
    assert signal.independent_sources == 2
    assert signal.sample_size == 2
    assert signal.frequency == 1.0
    assert signal.confidence == "medium"


def test_high_confidence_requires_four_sources_and_half_sample():
    records = []

    for index in range(1, 7):
        records.append(
            _record(
                evidence_id=(
                    f"role-{index}"
                ),
                job_id=str(index),
                signal_type=(
                    "role_family"
                ),
                statement=(
                    "Product Operations"
                ),
                recommendation="best_match",
                current_fit=80,
            )
        )

    for index in range(1, 5):
        records.append(
            _record(
                evidence_id=(
                    f"blocker-{index}"
                ),
                job_id=str(index),
                signal_type=(
                    "best_match_blocker"
                ),
                statement="SQL",
                recommendation="best_match",
                current_fit=80,
            )
        )

    signals = aggregate_market_evidence(
        records
    )

    sql = next(
        item
        for item in signals
        if (
            item.signal_type
            == "best_match_blocker"
        )
    )

    assert sql.independent_sources == 4
    assert sql.sample_size == 6
    assert sql.frequency == 0.6667
    assert sql.confidence == "high"


def test_low_confidence_for_single_observation():
    records = [
        _record(
            evidence_id="e1",
            job_id="1",
            signal_type="market_strength",
            statement=(
                "Stakeholder Communication"
            ),
            recommendation="best_match",
            current_fit=85,
        ),
        _record(
            evidence_id="role-2",
            job_id="2",
            signal_type="role_family",
            statement="Product Operations",
            recommendation="best_match",
            current_fit=80,
        ),
    ]

    signals = aggregate_market_evidence(
        records
    )

    strength = next(
        item
        for item in signals
        if (
            item.signal_type
            == "market_strength"
        )
    )

    assert strength.independent_sources == 1
    assert strength.sample_size == 2
    assert strength.frequency == 0.5
    assert strength.confidence == "low"


def test_blocker_denominator_uses_near_market_jobs():
    records = [
        _record(
            evidence_id="e1",
            job_id="1",
            signal_type=(
                "best_match_blocker"
            ),
            statement="SQL",
            recommendation="reject",
            current_fit=55,
        ),
        _record(
            evidence_id="role-2",
            job_id="2",
            signal_type="role_family",
            statement="Data Operations",
            recommendation="reject",
            current_fit=20,
        ),
    ]

    signals = aggregate_market_evidence(
        records
    )

    blocker = next(
        item
        for item in signals
        if (
            item.signal_type
            == "best_match_blocker"
        )
    )

    assert blocker.sample_size == 1
    assert blocker.frequency == 1.0
    assert blocker.confidence == "low"


def test_same_signal_tracks_multiple_role_families():
    records = [
        _record(
            evidence_id="e1",
            job_id="1",
            signal_type=(
                "best_match_blocker"
            ),
            statement="SQL",
            recommendation="potential",
            current_fit=70,
            role_family=(
                "Product Operations"
            ),
        ),
        _record(
            evidence_id="e2",
            job_id="2",
            signal_type=(
                "best_match_blocker"
            ),
            statement="SQL",
            recommendation="potential",
            current_fit=72,
            role_family=(
                "Operations Analytics"
            ),
        ),
    ]

    signal = aggregate_market_evidence(
        records
    )[0]

    assert signal.role_families == [
        "Operations Analytics",
        "Product Operations",
    ]


def test_non_market_evidence_is_ignored():
    records = [
        CareerEvidence(
            evidence_id="candidate-1",
            evidence_type=(
                "candidate_fact"
            ),
            signal_type="skill",
            source_ref=(
                "candidate:skills:sql"
            ),
            statement="SQL",
            authority="fact",
        )
    ]

    assert (
        aggregate_market_evidence(
            records
        )
        == []
    )


def test_duplicate_source_does_not_inflate_evidence_count_or_confidence():
    records = [
        _record(
            evidence_id=evidence_id,
            job_id="1",
            signal_type="best_match_blocker",
            statement="SQL",
            recommendation="potential",
            current_fit=70,
        )
        for evidence_id in ("duplicate-b", "duplicate-a")
    ]

    signal = aggregate_market_evidence(records)[0]

    assert signal.evidence_refs == ["duplicate-a"]
    assert signal.evidence_count == 1
    assert signal.independent_sources == 1
    assert signal.confidence == "low"


@pytest.mark.parametrize(
    ("sources", "sample_size", "expected"),
    [
        (0, 0, "low"),
        (1, 1, "low"),
        (2, 8, "medium"),
        (2, 9, "low"),
        (4, 8, "high"),
        (4, 9, "medium"),
    ],
)
def test_confidence_boundaries(sources, sample_size, expected):
    assert confidence_from_observations(
        independent_sources=sources,
        sample_size=sample_size,
    ) == expected
