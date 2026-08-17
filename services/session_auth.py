import streamlit as st

from models.app_user import AppUser


def get_current_user() -> AppUser | None:
    return st.session_state.get(
        "current_user"
    )


def login_user(
    user: AppUser,
) -> None:
    st.session_state.current_user = user


def logout_user() -> None:
    if "current_user" in st.session_state:
        del st.session_state["current_user"]


def require_login() -> AppUser:
    user = get_current_user()

    if user is None:
        st.warning(
            "Please log in to continue."
        )

        st.page_link(
            "pages/0_Login.py",
            label="Go to login",
        )

        st.stop()

    return user


def render_logout_button() -> None:
    user = get_current_user()

    if user is None:
        return

    with st.sidebar:
        st.caption(
            f"Signed in as {user.display_name}"
        )

        if st.button(
            "Log out",
            use_container_width=True,
            key="global_logout_button",
        ):
            logout_user()
            st.switch_page(
                "pages/0_Login.py"
            )
