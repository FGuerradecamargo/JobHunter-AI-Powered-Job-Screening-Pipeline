import streamlit as st

from models.app_user import AppUser
from services.authentication_runtime import logout_external_identity_if_active
from services.session_auth import get_authenticated_user, logout_user


def render_logout_button(*, authenticated_user: AppUser | None = None) -> None:
    # Callers may reuse authentication resolved during this same render only.
    user = authenticated_user if authenticated_user is not None else get_authenticated_user()
    if user is None:
        return

    with st.sidebar:
        st.caption(f"Signed in as {user.display_name}")
        if st.button(
            "Log out",
            use_container_width=True,
            key="global_logout_button",
        ):
            logout_user()
            logout_external_identity_if_active()
            st.rerun()
