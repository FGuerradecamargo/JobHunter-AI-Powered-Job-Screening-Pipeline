import logging

import streamlit as st
from components.workpilot_ui import apply_theme, page_header

from services.candidate_market_runtime import (
    load_candidate_market_runtime,
)
from services.market_profile_refresh_service import (
    MarketProfileRefreshService,
)
from components.auth_controls import render_logout_button
from services.session_auth import (
    require_authenticated_user,
)
from services.user_context_runtime import get_active_user_context


logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Improvements",
    page_icon=":material/trending_up:",
    layout="wide",
)

apply_theme()
page_header("Improvements", "Grounded priorities for your next step.")

authenticated_user = require_authenticated_user()
user_context = get_active_user_context(
    authenticated_user=authenticated_user
)
active_user = user_context.active_user
render_logout_button(authenticated_user=authenticated_user)

candidate_id = active_user.candidate_id

if not candidate_id:
    st.error("This profile does not have professional information yet.")
    st.stop()

market_refresh_failed = False

try:
    MarketProfileRefreshService().refresh()
except Exception:
    logger.exception(
        "Could not refresh global public MarketProfile."
    )
    market_refresh_failed = True

try:
    runtime = load_candidate_market_runtime(candidate_id)
except Exception:
    logger.exception("Could not load CandidateMarket.")
    st.error("Your improvement plan could not be loaded.")
    st.stop()

status = runtime["status"]

if market_refresh_failed:
    st.caption(
        "The latest public market evidence could not be refreshed. "
        "Any previously saved public Market snapshot is preserved."
    )

if status == "candidate_unavailable":
    st.info(
        "Your current professional profile is not available yet."
    )
    st.stop()

if status == "direction_unavailable":
    st.info(
        "Choose a career direction before WorkPilot prioritises "
        "market-based improvements."
    )
    st.stop()

if status == "market_unavailable":
    st.info(
        "WorkPilot does not yet have enough public market evidence "
        "for your current direction."
    )
    st.caption(
        "Missing market evidence is not treated as a skill gap."
    )
    st.stop()


band_titles = {
    "now": "NOW",
    "next": "NEXT",
    "watch": "WATCH",
}

kind_explanations = {
    "build": "A confirmed gap that appears in this market.",
    "prove": "You have relevant or transferable evidence worth making clearer.",
    "explore": (
        "The market signal exists, but WorkPilot cannot tell from "
        "your current evidence whether this is a gap."
    ),
}


for entry in runtime["segments"]:
    market = entry["market_profile"]
    assessment = entry["assessment"]
    plan = entry["plan"]
    segment = market.segment

    st.divider()

    title = segment.role_family or "Observed market"
    st.subheader(title)

    scope = [
        value
        for value in (
            segment.location,
            segment.seniority,
            segment.domain,
        )
        if value
    ]

    if scope:
        st.caption(" / ".join(scope))

    metrics = st.columns(3)
    metrics[0].metric("Observed jobs", market.sample_size)
    metrics[1].metric("Market signals", len(assessment.signals))
    metrics[2].metric("Market version", market.profile_version)

    if market.uncertainties:
        with st.expander("Evidence limits", expanded=False):
            for uncertainty in market.uncertainties:
                st.write(
                    "- " + uncertainty.replace("_", " ").capitalize()
                )

    for band in ("now", "next", "watch"):
        st.markdown(f"### {band_titles[band]}")

        items = [
            item
            for item in plan.improvements
            if item.band.value == band
        ]

        if not items:
            if band == "now":
                st.caption(
                    "No supported priority needs your attention now."
                )
            elif band == "next":
                st.caption(
                    "No supported next priority is available yet."
                )
            else:
                st.caption(
                    "There is nothing additional to watch right now."
                )
            continue

        for item in items:
            kind = item.kind.value

            with st.expander(
                f"{kind.upper()} / {item.label}",
                expanded=(band == "now"),
            ):
                st.write(item.why)

                st.caption(
                    kind_explanations[kind]
                )

                frequency = round(item.frequency * 100)

                st.caption(
                    f"Observed in {frequency}% of this "
                    f"{market.sample_size}-job sample | "
                    f"{item.market_confidence.title()} market confidence"
                )

                if item.candidate_evidence_refs:
                    st.caption(
                        f"{len(item.candidate_evidence_refs)} "
                        "candidate evidence reference(s)"
                    )

                if item.source_job_ids:
                    st.caption(
                        f"{len(item.source_job_ids)} "
                        "independent job source(s)"
                    )

st.divider()
st.caption(
    "These recommendations are decision support. "
    "They do not change your professional evidence or career direction."
)
