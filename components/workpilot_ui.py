"""Presentation only. Domain decisions remain in the existing services."""
from html import escape
from pathlib import Path

import streamlit as st


def apply_theme():
    st.html("<style>" + Path(__file__).with_name("workpilot.css").read_text(encoding="utf-8") + "</style>")


def page_header(title, subtitle="", *, eyebrow="WORKPILOT"):
    st.html(f'<header class="wp-page-header"><p class="wp-eyebrow">{escape(eyebrow)}</p>'
            f'<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></header>')


def status_badge(label, tone="neutral"):
    tone = tone if tone in {"neutral", "positive", "attention"} else "neutral"
    st.html(f'<span class="wp-badge wp-badge-{tone}">{escape(str(label))}</span>')


def empty_state(title, description):
    st.html(f'<section class="wp-empty"><h3>{escape(title)}</h3><p>{escape(description)}</p></section>')


def render_profile_snapshot(profile):
    if profile is None:
        empty_state("Your professional story starts here", "No confirmed profile snapshot is available yet.")
        return
    st.subheader("Current position")
    st.write(profile.checkpoint.current_position or "Not yet established")
    st.caption(f"Profile v{profile.profile_version} | Derived from confirmed career evidence")
    st.subheader("Current direction")
    for objective in profile.objectives:
        st.write(objective)
    if not profile.objectives:
        st.caption("No current direction recorded.")
    for title, values in (("Proven capabilities", profile.checkpoint.proven_strengths),
                          ("Transferable capabilities", profile.checkpoint.transferable_strengths)):
        st.subheader(title)
        for item in values:
            st.write(item)
        if not values:
            st.caption("Not yet established in the current profile.")
    st.subheader("Evidence to clarify")
    for item in profile.evidence_gaps:
        st.write(item)
    if not profile.evidence_gaps:
        st.caption("No evidence questions recorded. This is not proof that every requirement is met.")
