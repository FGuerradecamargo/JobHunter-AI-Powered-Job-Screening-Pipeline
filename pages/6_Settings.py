import streamlit as st

from components.workpilot_ui import apply_theme, page_header, status_badge
from services.session_auth import require_authenticated_user, render_logout_button
from services.user_context_runtime import get_active_user_context
from services.candidate_product_state_repository import CandidateProductStateRepository
from services.candidate_product_state_service import HiredTransitionService
from services.product_mode_policy import product_mode_policy

authenticated = require_authenticated_user()
active = get_active_user_context(authenticated_user=authenticated).active_user
apply_theme()
page_header("Settings", "Account, connections and product access.")
render_logout_button(authenticated_user=authenticated)
st.subheader("Account")
st.write(authenticated.display_name)
if active.id != authenticated.id:
    st.info("Administrative profile view is active.")
if active.candidate_id:
    state = CandidateProductStateRepository().get(active.candidate_id)
    policy = product_mode_policy(state)
    st.subheader("Product mode")
    status_badge(state.mode.value.replace("_", " ").title())
    if state.subscription_end_requested:
        st.info("Subscription end requested. Billing confirmation is pending; this is not a cancellation confirmation.")
    else:
        st.caption("No billing provider is connected. Product intent does not confirm billing changes.")
    if policy.can_return_to_search and active.id == authenticated.id:
        if st.button("Return to Search", icon=":material/work:"):
            HiredTransitionService().return_to_search(candidate_id=active.candidate_id)
            st.rerun()
    st.divider()
    st.subheader("Connections & sources")
    if policy.show_sources:
        st.page_link("pages/2_Sources.py", label="Manage sources", icon=":material/link:")
    else:
        st.caption("Connections cannot be changed with read-only access.")
    st.caption("Gmail and imported evidence retain their source ownership and visibility.")
