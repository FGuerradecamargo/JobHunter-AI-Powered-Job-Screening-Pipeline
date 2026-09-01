from services.database import (
    _candidate_job_reanalysis_reasons,
)


def test_no_reanalysis_when_all_signatures_match():
    reasons = (
        _candidate_job_reanalysis_reasons(
            stored_evidence_signature="e1",
            stored_direction_signature="d1",
            stored_constraint_signature="c1",
            current_evidence_signature="e1",
            current_direction_signature="d1",
            current_constraint_signature="c1",
        )
    )

    assert reasons == []


def test_evidence_change_is_identified():
    reasons = (
        _candidate_job_reanalysis_reasons(
            stored_evidence_signature="old-e",
            stored_direction_signature="d1",
            stored_constraint_signature="c1",
            current_evidence_signature="new-e",
            current_direction_signature="d1",
            current_constraint_signature="c1",
        )
    )

    assert reasons == [
        "evidence",
    ]


def test_direction_and_constraint_changes_are_identified():
    reasons = (
        _candidate_job_reanalysis_reasons(
            stored_evidence_signature="e1",
            stored_direction_signature="old-d",
            stored_constraint_signature="old-c",
            current_evidence_signature="e1",
            current_direction_signature="new-d",
            current_constraint_signature="new-c",
        )
    )

    assert reasons == [
        "direction",
        "constraint",
    ]


def test_all_changes_keep_deterministic_reason_order():
    reasons = (
        _candidate_job_reanalysis_reasons(
            stored_evidence_signature="old-e",
            stored_direction_signature="old-d",
            stored_constraint_signature="old-c",
            current_evidence_signature="new-e",
            current_direction_signature="new-d",
            current_constraint_signature="new-c",
        )
    )

    assert reasons == [
        "evidence",
        "direction",
        "constraint",
    ]


def test_missing_legacy_signatures_are_stale():
    reasons = (
        _candidate_job_reanalysis_reasons(
            stored_evidence_signature=None,
            stored_direction_signature=None,
            stored_constraint_signature=None,
            current_evidence_signature="e1",
            current_direction_signature="d1",
            current_constraint_signature="c1",
        )
    )

    assert reasons == [
        "evidence",
        "direction",
        "constraint",
    ]
