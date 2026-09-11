from models.candidate import Candidate
from models.career_update import CareerUpdate

from services.career_evidence_builder import (
    build_career_evidence_records,
)


def _candidate() -> Candidate:
    return Candidate(
        id="candidate-1",
        name="Test Candidate",
        current_role="Customer Operations",
        current_level="Specialist",
        professional_summary="",
        skills=[
            "Python",
        ],
        strengths=[
            "Stakeholder Communication",
        ],
        proven_capabilities=[
            "Complex customer escalation",
        ],
        technical_tools=[
            "Zendesk",
        ],
        domain_experience=[
            "Customer Operations",
        ],
    )


def test_builds_candidate_fact_evidence():
    records = build_career_evidence_records(
        candidate=_candidate(),
    )

    signals = {
        (
            item.signal_type,
            item.statement,
            item.authority,
        )
        for item in records
    }

    assert (
        "skill",
        "Python",
        "fact",
    ) in signals

    assert (
        "proven_capability",
        "Complex customer escalation",
        "fact",
    ) in signals


def test_builds_traceable_market_evidence():
    records = build_career_evidence_records(
        candidate=_candidate(),
        market_signals=[
            {
                "job_id": "job-1",
                "recommendation": (
                    "best_match"
                ),
                "current_fit": 82,
                "market_signal": {
                    "role_family": (
                        "Product Operations"
                    ),
                    "market_strengths": [
                        "Stakeholder Communication",
                    ],
                    "best_match_blockers": [
                        "SQL",
                    ],
                    "what_would_raise_fit": [
                        "Demonstrated SQL projects",
                    ],
                },
            }
        ],
    )

    blocker = next(
        item
        for item in records
        if (
            item.signal_type
            == "best_match_blocker"
        )
    )

    assert blocker.statement == "SQL"
    assert blocker.source_ref == "job:job-1"
    assert (
        blocker.role_family
        == "Product Operations"
    )
    assert blocker.authority == (
        "market_evidence"
    )
    assert blocker.metadata[
        "current_fit"
    ] == 82


def test_builds_career_update_and_outcome_evidence():
    records = build_career_evidence_records(
        candidate=_candidate(),
        career_updates=[
            CareerUpdate(
                id="update-1",
                candidate_id="candidate-1",
                update_type="new_skill",
                description="Completed SQL course",
                created_at="2026-09-01",
            )
        ],
        application_outcomes=[
            {
                "job_id": "job-2",
                "final_status": "interview",
                "interview_stage": "screen",
                "outcome_date": "2026-09-10",
            }
        ],
    )

    assert any(
        item.evidence_type
        == "career_update"
        and item.statement
        == "Completed SQL course"
        for item in records
    )

    assert any(
        item.evidence_type
        == "application_outcome"
        and item.statement
        == "interview"
        and item.authority
        == "outcome"
        for item in records
    )


def test_evidence_id_is_stable_for_formatting_noise():
    first = _candidate()
    second = _candidate()

    first.skills = [
        "Python",
    ]

    second.skills = [
        "  PYTHON  ",
    ]

    first_record = next(
        item
        for item in build_career_evidence_records(
            candidate=first
        )
        if item.signal_type == "skill"
    )

    second_record = next(
        item
        for item in build_career_evidence_records(
            candidate=second
        )
        if item.signal_type == "skill"
    )

    assert (
        first_record.evidence_id
        == second_record.evidence_id
    )


def test_duplicate_evidence_is_collapsed():
    candidate = _candidate()

    candidate.skills = [
        "Python",
        "Python",
    ]

    records = build_career_evidence_records(
        candidate=candidate
    )

    python_records = [
        item
        for item in records
        if (
            item.signal_type == "skill"
            and item.statement == "Python"
        )
    ]

    assert len(python_records) == 1
