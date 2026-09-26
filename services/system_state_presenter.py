"""Pure safe copy. No IO, retries, outcome changes or inferred professional facts."""
from datetime import datetime, timezone

from models.system_state import ApplicationAgeState, SearchRunState, SystemNotice, SystemNoticeKind


def search_notice(state: SearchRunState) -> SystemNotice:
    notices = {
        SearchRunState.STARTING: SystemNotice("search_starting", "Getting things ready...",
            "Preparing the search using your current profile and priorities.", SystemNoticeKind.INFO),
        SearchRunState.SEARCHING: SystemNotice("searching", "Searching for opportunities...",
            "WorkPilot is still searching.", SystemNoticeKind.INFO, "Stop search"),
        SearchRunState.STOPPED: SystemNotice("search_stopped", "Search stopped.",
            "Already saved opportunities are still here.", SystemNoticeKind.INFO, "Search again"),
        SearchRunState.COMPLETED: SystemNotice("search_completed", "Search complete.",
            "Your search results are available.", SystemNoticeKind.SUCCESS),
        SearchRunState.NOTHING_WORTHWHILE: SystemNotice("nothing_worthwhile", "No recommendations yet.",
            "This search did not produce recommendations from the jobs reviewed. This does not mean no suitable jobs exist.",
            SystemNoticeKind.INFO, "Adjust search", "Search again"),
        SearchRunState.ERROR: SystemNotice("search_error", "Search could not finish.",
            "Search could not finish. Already saved opportunities are kept. You can start a new search.",
            SystemNoticeKind.ERROR, "Try again"),
    }
    return notices[SearchRunState(state)]


def _count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("A nonnegative observed counter is required.")
    return value


def search_progress_message(*, reviewed, ai_eligible, buffered, batch_max):
    for value in (reviewed, ai_eligible, buffered, batch_max):
        _count(value)
    if batch_max == 0 or buffered > batch_max:
        raise ValueError("Invalid analysis buffer size.")
    notice = search_notice(SearchRunState.SEARCHING)
    return (f"{notice.title}\n\nReviewed: {reviewed}\n\n"
            f"Passed initial screening: {ai_eligible}\n\n"
            f"Preparing deeper analysis: {buffered}/{batch_max}\n\n{notice.message}")


def stopped_search_message(*, opportunities_kept):
    return f"Search stopped. {_count(opportunities_kept)} opportunities kept."


def analysis_unavailable_notice():
    return SystemNotice("analysis_unavailable", "Deeper analysis is temporarily unavailable.",
        "We couldn't continue the deeper analysis right now. Your existing results are safe, "
        "and these opportunities can be analyzed again later.", SystemNoticeKind.ATTENTION)


def gmail_notice(*, connected: bool, needs_reconnect: bool = False):
    if needs_reconnect:
        return SystemNotice("gmail_reconnect", "Gmail needs to be reconnected.",
            "You can keep using WorkPilot. Reconnect Gmail before importing new job-alert emails.",
            SystemNoticeKind.ATTENTION, "Reconnect Gmail")
    if connected:
        return None
    return SystemNotice("gmail_disconnected", "Gmail is not connected.",
        "You can still use WorkPilot normally. Connect Gmail to import opportunities from job alerts.",
        SystemNoticeKind.INFO, "Connect Gmail")


def profile_information_notice():
    # Do not interpolate raw model/provider errors into user-facing copy.
    return SystemNotice("profile_needs_information", "More information is needed.",
        "Review the open questions in your profile and add evidence where available.",
        SystemNoticeKind.ATTENTION, "Review profile")


def stale_analysis_notice():
    return SystemNotice("analysis_stale", "This analysis needs an update.",
        "Update the analysis to use the current profile and job information.",
        SystemNoticeKind.ATTENTION, "Update analysis")


def empty_applications_notice(*, has_history: bool):
    if has_history:
        return SystemNotice("applications_no_active", "Nothing active right now.",
            "Your previous applications remain in your history.", SystemNoticeKind.INFO)
    return SystemNotice("applications_empty", "No applications yet.",
        "Applications appear here after you confirm that you applied.", SystemNoticeKind.INFO, "Explore jobs")


def empty_improvements_notice(*, enough_evidence: bool):
    if enough_evidence:
        return SystemNotice("improvements_empty", "No supported actions right now.",
            "The current evidence does not suggest an improvement action. Revisit when your context changes.",
            SystemNoticeKind.INFO)
    return SystemNotice("improvements_learning", "We are still learning what matters.",
        "More profile and market evidence is needed before suggesting improvements.", SystemNoticeKind.INFO)


def dashboard_clear_notice():
    return SystemNotice("dashboard_clear", "You are all caught up.",
        "There are no pending actions in this view.", SystemNoticeKind.SUCCESS)


def application_age_state(*, applied_at: str, now: str) -> ApplicationAgeState | None:
    def timestamp(value):
        parsed = datetime.fromisoformat(value)
        # Existing UTC database timestamps may omit an explicit offset.
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    try:
        applied, current = timestamp(applied_at), timestamp(now)
    except (ValueError, TypeError):
        return None
    if current < applied:
        return None
    days = (current - applied).days
    band, prompt = ("fresh", "") if days < 10 else (("aging", "Still waiting?") if days < 21 else ("old", "No update yet?"))
    return ApplicationAgeState(days, band, f"Applied {days} day{'s' if days != 1 else ''} ago", prompt)
