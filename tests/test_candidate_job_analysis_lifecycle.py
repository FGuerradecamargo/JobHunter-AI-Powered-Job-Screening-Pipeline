import pytest

from services.candidate_job_analysis_service import (
    _resolve_persistence_lifecycle,
)


def test_discovery_approved_keeps_current_behavior():
    status, opportunity_state = (
        _resolve_persistence_lifecycle(
            source_row={
                "status": "in_review",
                "opportunity_state": "none",
            },
            analysis_status="in_review",
            preserve_existing_lifecycle=False,
        )
    )

    assert status == "in_review"
    assert opportunity_state == "none"


def test_discovery_reject_keeps_current_behavior():
    status, opportunity_state = (
        _resolve_persistence_lifecycle(
            source_row={
                "status": "in_review",
                "opportunity_state": "none",
            },
            analysis_status="system_rejected",
            preserve_existing_lifecycle=False,
        )
    )

    assert status == "system_rejected"
    assert opportunity_state == "none"


def test_reanalysis_none_can_become_system_rejected():
    status, opportunity_state = (
        _resolve_persistence_lifecycle(
            source_row={
                "status": "in_review",
                "opportunity_state": "none",
            },
            analysis_status="system_rejected",
            preserve_existing_lifecycle=True,
        )
    )

    assert status == "system_rejected"
    assert opportunity_state == "none"


def test_reanalysis_active_approved_preserves_active():
    status, opportunity_state = (
        _resolve_persistence_lifecycle(
            source_row={
                "status": "in_review",
                "opportunity_state": "active",
            },
            analysis_status="in_review",
            preserve_existing_lifecycle=True,
        )
    )

    assert status == "in_review"
    assert opportunity_state == "active"


def test_reanalysis_active_reject_preserves_active():
    status, opportunity_state = (
        _resolve_persistence_lifecycle(
            source_row={
                "status": "in_review",
                "opportunity_state": "active",
            },
            analysis_status="system_rejected",
            preserve_existing_lifecycle=True,
        )
    )

    assert status == "in_review"
    assert opportunity_state == "active"


def test_reanalysis_refuses_application_or_outcome_state():
    with pytest.raises(
        ValueError,
        match="unsupported opportunity lifecycle",
    ):
        _resolve_persistence_lifecycle(
            source_row={
                "status": "applied",
                "opportunity_state": "applied",
            },
            analysis_status="in_review",
            preserve_existing_lifecycle=True,
        )
