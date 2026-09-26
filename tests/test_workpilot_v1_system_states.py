from dataclasses import fields
import pytest

from models.system_state import ApplicationAgeState, SearchRunState, SystemNoticeKind
from services.system_state_presenter import (
    application_age_state, empty_applications_notice, empty_improvements_notice,
    gmail_notice, search_notice, search_progress_message, stopped_search_message,
    analysis_unavailable_notice, profile_information_notice, stale_analysis_notice,
    dashboard_clear_notice,
)


@pytest.mark.parametrize("state", list(SearchRunState))
def test_every_search_state_has_unique_safe_copy(state):
    notice = search_notice(state)
    assert notice.code and notice.title and notice.message
    assert len({search_notice(s).code for s in SearchRunState}) == len(SearchRunState)
    if state in (SearchRunState.STARTING, SearchRunState.SEARCHING):
        assert notice.kind is SystemNoticeKind.INFO
        assert "found 0" not in notice.message


def test_stopped_search_preserves_results_and_does_not_promise_resume():
    notice = search_notice(SearchRunState.STOPPED)
    assert "still here" in notice.message
    assert notice.primary_action == "Search again"
    assert stopped_search_message(opportunities_kept=3) == "Search stopped. 3 opportunities kept."


def test_no_recommendations_does_not_claim_global_pool_empty():
    assert "does not mean no suitable jobs exist" in search_notice(SearchRunState.NOTHING_WORTHWHILE).message


def test_running_uses_only_supplied_observed_counts():
    message = search_progress_message(reviewed=22, ai_eligible=20, buffered=3, batch_max=10)
    assert "Reviewed: 22" in message and "Preparing deeper analysis: 3/10" in message
    assert "Passed initial screening: 20" in message
    assert "still searching" in message
    assert "I found" not in message


@pytest.mark.parametrize("bad", [-1, None, True, "3"])
def test_missing_or_invalid_counter_is_not_fabricated(bad):
    with pytest.raises(ValueError):
        search_progress_message(reviewed=bad, ai_eligible=0, buffered=0, batch_max=10)


def test_impossible_buffer_rejected():
    with pytest.raises(ValueError):
        search_progress_message(reviewed=22, ai_eligible=20, buffered=11, batch_max=10)


def test_gmail_states_are_optional_and_nonblocking():
    assert gmail_notice(connected=True) is None
    assert gmail_notice(connected=True, needs_reconnect=True).primary_action == "Reconnect Gmail"
    assert "still use WorkPilot normally" in gmail_notice(connected=False).message


def test_unknown_evidence_is_not_no_improvement_needed():
    ready = empty_improvements_notice(enough_evidence=True)
    learning = empty_improvements_notice(enough_evidence=False)
    assert ready.code != learning.code
    assert "More profile and market evidence" in learning.message
    assert "keep watching" not in ready.message  # No fictional background monitoring.


def test_history_and_empty_are_distinct():
    assert empty_applications_notice(has_history=True).code != empty_applications_notice(has_history=False).code
    assert "history" in empty_applications_notice(has_history=True).message
    assert "confirm" in empty_applications_notice(has_history=False).message


@pytest.mark.parametrize("days,band", [(0,"fresh"),(9,"fresh"),(10,"aging"),(20,"aging"),(21,"old"),(29,"old")])
def test_age_is_attention_only_at_deterministic_boundaries(days, band):
    state = application_age_state(applied_at="2026-09-01T12:00:00Z", now=f"2026-09-{days+1:02d}T12:00:00Z")
    assert state.band == band and state.days_since_applied == days
    assert {f.name for f in fields(ApplicationAgeState)} == {"days_since_applied", "band", "title", "action_prompt"}


@pytest.mark.parametrize("value", ["", "invalid", None, "2027-01-01T00:00:00Z"])
def test_missing_invalid_future_dates_remain_unknown(value):
    assert application_age_state(applied_at=value, now="2026-09-27T00:00:00Z") is None


def test_age_accepts_legacy_utc_and_normalizes_offsets():
    state = application_age_state(applied_at="2026-09-01T12:00:00", now="2026-09-02T13:00:00+01:00")
    assert state.days_since_applied == 1


def test_safe_static_errors_have_no_provider_or_private_payload():
    notices = [analysis_unavailable_notice(), profile_information_notice(), stale_analysis_notice(), dashboard_clear_notice()]
    for notice in notices:
        assert "OpenAI" not in notice.message
        assert "exception" not in notice.message
    assert "existing results are safe" in analysis_unavailable_notice().message
