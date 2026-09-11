import logging

import streamlit as st

from services.career_intelligence_presenter import (
    CONFIDENCE_EXPLANATION,
    build_career_intelligence_view,
    load_career_intelligence_snapshot,
)
from services.session_auth import render_logout_button, require_authenticated_user
from services.user_context_runtime import get_active_user_context


logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Improvements",
    page_icon=":material/trending_up:",
    layout="wide",
)
st.caption("CAREER INTELLIGENCE")
st.title("Improvements")
st.write(
    "A checkpoint based on the market opportunities WorkPilot has observed. "
    "It supports your decisions; it does not define your career."
)

authenticated_user = require_authenticated_user()
user_context = get_active_user_context(authenticated_user=authenticated_user)
active_user = user_context.active_user
render_logout_button()

candidate_id = active_user.candidate_id
if not candidate_id:
    st.error("This profile does not have professional information yet.")
    st.stop()

try:
    with st.spinner("Building your current career intelligence checkpoint..."):
        snapshot = load_career_intelligence_snapshot(candidate_id)
        view = build_career_intelligence_view(snapshot)
except Exception:
    logger.exception("Could not build the Career Intelligence snapshot.")
    st.error("Your career intelligence checkpoint could not be loaded.")
    st.stop()


def show_labels(labels, empty_message):
    if labels:
        for label in labels:
            st.write(f"- {label}")
    else:
        st.caption(empty_message)


def show_priority(priority):
    with st.expander(priority["title"], expanded=False):
        st.write(priority["why_now"])
        st.caption(
            f'{priority["category_label"]} · '
            f'{priority["confidence_label"]} · '
            f'{priority["direction_label"]}'
        )
        if priority["role_families"]:
            st.write("Role families: " + ", ".join(priority["role_families"]))
        st.caption(f'{priority["source_count"]} observed source(s)')
        if priority["related_objective"]:
            st.caption("Related objective: " + priority["related_objective"])
        st.caption("Evidence references: " + str(priority["evidence_count"]))


position = view["current_position"]
st.subheader("Current position")
metric_columns = st.columns(4)
metric_columns[0].metric("Observed jobs", position["sample_size"])
metric_columns[1].metric("Best Matches", position["best_match_count"])
metric_columns[2].metric("Near matches", position["near_match_count"])
metric_columns[3].metric("Average fit", position["average_fit_label"])

st.subheader("Direction alignment")
if not view["direction_known"]:
    st.info(
        "No career direction is currently selected. WorkPilot can show what "
        "the observed market suggests, but it will not choose a direction for you."
    )

alignment_columns = st.columns(3)
with alignment_columns[0]:
    st.markdown("**Competitive now**")
    show_labels(position["competitive_now"], "No recurring competitive family yet.")
with alignment_columns[1]:
    st.markdown("**Bridge**")
    show_labels(position["bridge"], "No bridge family observed yet.")
with alignment_columns[2]:
    st.markdown("**Target**")
    show_labels(position["target"], "No explicit target selected.")

if position["sample_size"] == 0:
    st.info(
        "Analyze job opportunities first so WorkPilot can identify recurring "
        "market patterns."
    )

st.subheader("Competitive advantages")
if view["advantages"]:
    for advantage in view["advantages"]:
        with st.expander(advantage["signal"], expanded=False):
            st.caption(
                f'{advantage["confidence_label"]} · '
                f'{advantage["evidence_count"]} evidence reference(s)'
            )
            if advantage["role_families"]:
                st.write("Observed across: " + ", ".join(advantage["role_families"]))
else:
    st.info("The observed market does not show a supported advantage yet.")

st.subheader("Recurring blockers")
if view["blockers"]:
    for blocker in view["blockers"]:
        with st.expander(blocker["blocker"], expanded=False):
            st.caption(
                f'{blocker["direction_label"]} · '
                f'{blocker["confidence_label"]} · '
                f'{blocker["evidence_count"]} evidence reference(s)'
            )
            if blocker["role_families"]:
                st.write("Affects: " + ", ".join(blocker["role_families"]))
else:
    st.info("The current observed sample does not show a recurring blocker yet.")

st.subheader("Improvements")
band_labels = {"now": "Now", "next": "Next", "watch": "Watch"}
for band in ("now", "next", "watch"):
    st.markdown(f'### {band_labels[band]}')
    items = view["priorities"][band]
    if items:
        for priority in items:
            show_priority(priority)
    else:
        st.caption(view["priority_empty_messages"][band])

st.subheader("Longer-term distances")
if view["structural_distances"]:
    st.write(
        "These are experience gaps to keep in view, not quick tasks or promises."
    )
    for distance in view["structural_distances"]:
        with st.expander(distance["blocker"], expanded=False):
            st.caption(
                f'{distance["direction_label"]} · '
                f'{distance["confidence_label"]}'
            )
            if distance["role_families"]:
                st.write("Affects: " + ", ".join(distance["role_families"]))
else:
    st.caption("No structural distance is supported by the current evidence.")

with st.expander("Evidence and confidence", expanded=False):
    st.write(view["checkpoint_summary"])
    st.write(CONFIDENCE_EXPLANATION)
    st.caption("Snapshot version: " + view["schema_version"])
