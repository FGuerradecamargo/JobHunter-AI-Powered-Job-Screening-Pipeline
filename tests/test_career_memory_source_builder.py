from copy import deepcopy

from models.candidate import Candidate
from models.career_objective import (
    CareerObjective,
)
from models.career_update import CareerUpdate

from services.career_memory_source_builder import (
    build_career_memory_source_payload,
    build_source_signature,
)


def _candidate(
    *,
    skills=None,
) -> Candidate:
    return Candidate(
        id="candidate-test",
        name="Test Candidate",
        current_role="Customer Operations",
        current_level="Specialist",
        professional_summary=(
            "Operations professional"
        ),
        skills=skills or [
            "Python",
            "Technical Support",
        ],
        target_role_families=[
            "Technical Support Engineering",
            "Fraud & Risk Analytics",
        ],
        bridge_role_families=[
            "Technical Support",
        ],
        competitive_role_families=[
            "Customer Operations",
        ],
    )


def _objective(
    *,
    updated_at="2026-08-01",
) -> CareerObjective:
    return CareerObjective(
        id="objective-1",
        candidate_id="candidate-test",
        title="Move toward technical support",
        description=(
            "Prioritize technical support roles."
        ),
        active=True,
        desired_role_families=[
            "Technical Support Engineering",
        ],
        created_at="2026-01-01",
        updated_at=updated_at,
    )


def _payload(
    *,
    candidate=None,
    objective=None,
    updates=None,
    market=None,
    outcomes=None,
):
    return build_career_memory_source_payload(
        candidate=(
            candidate
            or _candidate()
        ),
        objective=(
            objective
            if objective is not None
            else _objective()
        ),
        career_updates=(
            updates
            if updates is not None
            else []
        ),
        market_position=(
            market
            if market is not None
            else {
                "historical": {
                    "sample_size": 10,
                    "average_fit": 67.5,
                    "role_families": [],
                },
                "current_batch": {},
            }
        ),
        application_outcomes=(
            outcomes
            if outcomes is not None
            else []
        ),
    )


def test_signature_is_stable_for_unordered_candidate_lists():
    first = _payload(
        candidate=_candidate(
            skills=[
                "Python",
                "Technical Support",
            ]
        )
    )

    second = _payload(
        candidate=_candidate(
            skills=[
                "Technical Support",
                "Python",
            ]
        )
    )

    assert (
        build_source_signature(first)
        == build_source_signature(second)
    )


def test_objective_timestamps_do_not_change_signature():
    first = _payload(
        objective=_objective(
            updated_at="2026-08-01"
        )
    )

    second = _payload(
        objective=_objective(
            updated_at="2026-08-31"
        )
    )

    assert (
        build_source_signature(first)
        == build_source_signature(second)
    )


def test_objective_semantic_change_changes_signature():
    first = _payload()

    changed = _objective()
    changed.description = (
        "Prioritize fraud analytics roles."
    )

    second = _payload(
        objective=changed
    )

    assert (
        build_source_signature(first)
        != build_source_signature(second)
    )


def test_new_career_update_changes_signature():
    first = _payload(
        updates=[]
    )

    second = _payload(
        updates=[
            CareerUpdate(
                id="update-1",
                candidate_id="candidate-test",
                update_type="skill",
                description=(
                    "Started SQL training"
                ),
                created_at="2026-08-31",
            )
        ]
    )

    assert (
        build_source_signature(first)
        != build_source_signature(second)
    )


def test_outcome_timestamp_noise_does_not_change_signature():
    first_outcome = {
        "job_id": "job-1",
        "final_status": "rejected",
        "interview_stage": "screen",
        "rejection_reason": "",
        "recruiter_feedback": "",
        "candidate_notes": "",
        "offer_salary": "",
        "offer_currency": "",
        "lessons_learned": "",
        "outcome_date": "2026-08-30",
        "created_at": "2026-08-30T10:00:00",
        "updated_at": "2026-08-30T10:00:00",
    }

    second_outcome = deepcopy(
        first_outcome
    )

    second_outcome["updated_at"] = (
        "2026-08-31T18:00:00"
    )

    first = _payload(
        outcomes=[
            first_outcome
        ]
    )

    second = _payload(
        outcomes=[
            second_outcome
        ]
    )

    assert (
        build_source_signature(first)
        == build_source_signature(second)
    )


def test_outcome_semantic_change_changes_signature():
    first_outcome = {
        "job_id": "job-1",
        "final_status": "in_process",
        "interview_stage": "screen",
        "outcome_date": "2026-08-30",
    }

    second_outcome = deepcopy(
        first_outcome
    )

    second_outcome[
        "final_status"
    ] = "offer"

    first = _payload(
        outcomes=[
            first_outcome
        ]
    )

    second = _payload(
        outcomes=[
            second_outcome
        ]
    )

    assert (
        build_source_signature(first)
        != build_source_signature(second)
    )


def test_market_evidence_change_changes_signature():
    first = _payload(
        market={
            "historical": {
                "sample_size": 10,
                "average_fit": 60.0,
            }
        }
    )

    second = _payload(
        market={
            "historical": {
                "sample_size": 11,
                "average_fit": 70.0,
            }
        }
    )

    assert (
        build_source_signature(first)
        != build_source_signature(second)
    )
