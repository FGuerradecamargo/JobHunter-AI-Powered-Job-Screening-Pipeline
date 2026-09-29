from datetime import datetime
from html import escape

import streamlit as st

from components.workpilot_ui import apply_theme, empty_state
from services.application_outcome_repository import ApplicationOutcomeRepository
from services.candidate_product_state_repository import CandidateProductStateRepository
from services.product_mode_policy import product_mode_policy
from services.database import list_candidate_jobs
from services.candidate_market_runtime import load_candidate_market_runtime
from services.profile_readiness_service import profile_readiness
from services.runtime_timing import timed_block, timed_page


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def _first_name(active_user) -> str:
    raw = str(getattr(active_user, "display_name", "") or "").strip()
    return raw.split()[0] if raw else "there"


def _mode_label(state) -> str:
    value = str(state.mode.value).lower()
    if value == "search":
        return "Search mode: Active"
    if value == "career":
        return "Career mode"
    return "Read-only mode"


def _bucket(job: dict) -> str:
    analysis = job.get("analysis", {}) or {}
    return str(analysis.get("bucket") or analysis.get("recommendation") or "")


def _opportunity_label(job: dict) -> str:
    return {
        "best_match": "Best Match",
        "potential": "Worth a Try",
        "good_opportunity": "You’re Strong, But",
    }.get(_bucket(job), "Opportunity")


def _attention_card(title: str, copy: str) -> None:
    st.html(
        f"""
        <article class="wp-attention-card">
          <div class="wp-attention-dot"></div>
          <div>
            <strong>{escape(title)}</strong>
            <p>{escape(copy)}</p>
          </div>
        </article>
        """
    )


def _small_opportunity(job: dict) -> None:
    title = escape(str(job.get("title") or "Opportunity"))
    company = escape(str(job.get("company") or "Company not listed"))
    label = escape(_opportunity_label(job))
    location = escape(str(job.get("location") or "Location not listed"))
    st.html(
        f"""
        <article class="wp-dashboard-opportunity">
          <div>
            <span class="wp-mini-label">{label}</span>
            <h4>{title}</h4>
            <p>{company} · {location}</p>
          </div>
          <span class="wp-arrow">→</span>
        </article>
        """
    )


def render_dashboard(active_user):
    apply_theme()
    candidate_id = active_user.candidate_id
    if not candidate_id:
        empty_state(
            "Start with your profile",
            "Your professional context is not available yet.",
        )
        return

    state = CandidateProductStateRepository().get(candidate_id)
    policy = product_mode_policy(state)

    name = escape(_first_name(active_user))
    st.html(
        f"""
        <header class="wp-dashboard-hero">
          <div>
            <p class="wp-eyebrow">TODAY</p>
            <h1>{escape(_greeting())}, {name}.</h1>
            <p>Here’s where things stand.</p>
          </div>
          <span class="wp-mode-pill">{escape(_mode_label(state))}</span>
        </header>
        """
    )

    with timed_block("profile"):
        readiness = profile_readiness(candidate_id)
        profile = readiness.snapshot
    with timed_block("applications"):
        applications = ApplicationOutcomeRepository().list_applications(candidate_id)
    with timed_block("opportunities"):
        opportunities = list_candidate_jobs(candidate_id, "in_review")
    ready = [item for item in applications if item.get("application_group") == "ready_to_apply"]
    applied = [item for item in applications if item.get("application_group") == "applied"]
    interviews = [item for item in applications if item.get("application_group") == "interview"]
    offers = [item for item in applications if item.get("application_group") == "offer"]
    active = [
        item for item in applications
        if item.get("application_group") in {"applied", "interview", "offer"}
    ]

    render_attention(ready, applied, interviews, offers)

    st.html('<div class="wp-dashboard-grid-marker"></div>')
    left, right = st.columns([1.15, 0.85], gap="large")

    with left:
        st.html(
            '<section class="wp-dashboard-panel-heading"><div><span class="wp-section-icon">↗</span>'
            '<h2>Your opportunities</h2></div></section>'
        )
        counts = {
            "Best Match": sum(_bucket(job) == "best_match" for job in opportunities),
            "Worth a Try": sum(_bucket(job) == "potential" for job in opportunities),
            "You’re Strong, But": sum(_bucket(job) == "good_opportunity" for job in opportunities),
        }
        st.html(
            '<div class="wp-opportunity-summary">'
            + ''.join(
                f'<div><strong>{count}</strong><span>{escape(label)}</span></div>'
                for label, count in counts.items()
            )
            + '</div>'
        )
        for job in opportunities[:2]:
            _small_opportunity(job)
        if not opportunities:
            st.caption("No current opportunity has crossed the recommendation threshold yet.")
        if policy.can_search and profile:
            st.page_link("pages/1_Opportunities.py", label="View all jobs →")

    with right:
        st.html(
            '<section class="wp-dashboard-panel-heading"><div><span class="wp-section-icon">□</span>'
            '<h2>Applications</h2></div></section>'
        )
        st.html(
            f"""
            <div class="wp-application-summary">
              <div class="wp-application-total"><strong>{len(active)}</strong><span>Active</span></div>
              <div class="wp-application-breakdown">
                <span>{len(applied)} Applied</span>
                <span>{len(interviews)} Interview</span>
                <span>{len(offers)} Offer</span>
              </div>
            </div>
            """
        )
        if interviews:
            st.info("Interview stage is your next application event.")
        elif offers:
            st.info("An offer is waiting for your decision.")
        elif applied:
            st.caption("Your active applications are waiting for updates.")
        else:
            st.caption("No active application needs attention right now.")
        st.page_link("pages/5_Applications.py", label="View applications →")

    render_market_sections(candidate_id)

    if profile:
        position = escape(str(profile.checkpoint.current_position or "Professional profile"))
        st.html(
            '<section class="wp-profile-strip"><div>'
            '<span class="wp-mini-label">YOUR PROFILE</span>'
            f'<h3>{position}</h3>'
            '<p>Up to date with your latest confirmed evidence.</p>'
            '</div></section>'
        )
        st.page_link("pages/3_Profile.py", label="Review profile →")
    else:
        st.html(
            '<section class="wp-profile-strip"><div>'
            '<span class="wp-mini-label">YOUR PROFILE</span>'
            '<h3>Needs attention</h3>'
            '<p>Complete your professional profile before relying on opportunity matching.</p>'
            '</div></section>'
        )
        st.page_link("pages/3_Profile.py", label="Continue profile →")

    if not policy.can_mutate:
        st.info("Read-only access. Your career and application history is preserved.")


@st.fragment
@timed_page("Dashboard")
def render_market_sections(candidate_id):
    if not st.button("Load market and next improvement", key=f"dashboard_market_{candidate_id}"):
        st.caption("Market right now and Your next improvement")
        return
    authorize_dashboard_candidate(candidate_id)
    with st.spinner("Loading current market evidence..."), timed_block("market"):
        try:
            runtime = load_candidate_market_runtime(candidate_id)
            improvement_items = [item for segment in runtime.get("segments", ())
                                 for item in segment["plan"].improvements]
        except Exception:
            st.info("Market context is temporarily unavailable. Your history is preserved.")
            return
    lower_left, lower_right = st.columns(2, gap="large")
    with lower_left:
        if improvement_items:
            item = improvement_items[0]
            st.html(
                '<section class="wp-dashboard-lower">'
                '<span class="wp-mini-label">MARKET RIGHT NOW</span>'
                f'<h3>{escape(str(item.label))}</h3>'
                f'<p>{escape(str(item.why))}</p></section>'
            )
        else:
            st.html(
                '<section class="wp-dashboard-lower">'
                '<span class="wp-mini-label">MARKET RIGHT NOW</span>'
                '<h3>No supported market signal yet</h3>'
                '<p>WorkPilot will show an insight here when current evidence supports one.</p>'
                '</section>'
            )

    with lower_right:
        if improvement_items:
            item = improvement_items[0]
            st.html(
                '<section class="wp-dashboard-lower">'
                '<span class="wp-mini-label">YOUR NEXT IMPROVEMENT</span>'
                f'<h3>{escape(str(item.label))}</h3>'
                f'<p>{escape(str(item.kind.value).title())} · {escape(str(item.band.value).title())}</p>'
                '</section>'
            )
            st.page_link("pages/4_Improvements.py", label="View improvements →")
        else:
            st.html(
                '<section class="wp-dashboard-lower">'
                '<span class="wp-mini-label">YOUR NEXT IMPROVEMENT</span>'
                '<h3>Nothing urgent to develop</h3>'
                '<p>No evidence-backed improvement is available yet.</p>'
                '</section>'
            )


def render_attention(ready, applied, interviews, offers):
    with st.container(key="dashboard_attention"):
        st.html(
            '<div class="wp-section-heading"><div><span class="wp-section-icon">!</span>'
            '<h2>Needs your attention</h2></div><span>Up to 3 items</span></div>'
        )

        attention = []
        if offers:
            attention.append(("Offer waiting for your decision", "Review the offer and choose your next step.", "applications"))
        if interviews:
            attention.append(("Interview to prepare for", "Your application is in interview stage.", "applications"))
        if ready:
            attention.append(("Application ready to review", "Your tailored application is ready for the next step.", "applications"))
        if applied and len(attention) < 3:
            attention.append(("Application waiting for an update", "Keep the status current when you hear back.", "applications"))

        attention = attention[:3]
        if attention:
            columns = st.columns(3, gap="medium")
            for index, (title, copy, destination) in enumerate(attention):
                with columns[index]:
                    _attention_card(title, copy)
                    if destination == "improvements":
                        st.page_link("pages/4_Improvements.py", label="View improvement →")
                    else:
                        st.page_link("pages/5_Applications.py", label="Open applications →")
        else:
            st.html(
                '<div class="wp-caught-up"><strong>You’re all caught up ✓</strong>'
                '<span>Nothing needs an immediate decision.</span></div>'
            )


def authorize_dashboard_candidate(candidate_id):
    from services.session_auth import require_authenticated_user
    from services.user_context_runtime import get_active_user_context
    actor = require_authenticated_user()
    context = get_active_user_context(authenticated_user=actor)
    if context.active_user.candidate_id != candidate_id:
        st.stop()
