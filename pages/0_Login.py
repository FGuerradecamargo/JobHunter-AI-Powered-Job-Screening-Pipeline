import streamlit as st

from services.auth_service import AuthService
from services.session_auth import (
    get_current_user,
    login_user,
    logout_user,
)


st.set_page_config(
    page_title="WorkPilot Login",
    page_icon="ðŸ”",
)

st.title("WorkPilot")

auth_service = AuthService()

current_user = get_current_user()


# ---------------------------------------------------------
# ALREADY LOGGED IN
# ---------------------------------------------------------

if current_user is not None:
    st.success(
        f"Logged in as {current_user.display_name}"
    )

    st.write(
        f"Access level: {current_user.access_level}"
    )

    if current_user.candidate_id:
        st.write(
            f"Profile: {current_user.candidate_id}"
        )

    if st.button(
        "Go to profile",
        type="primary",
    ):
        st.switch_page(
            "pages/3_Profile.py"
        )

    if st.button("Log out"):
        logout_user()
        st.rerun()

    st.stop()


# ---------------------------------------------------------
# LOGIN / SIGN UP
# ---------------------------------------------------------

login_tab, signup_tab = st.tabs(
    [
        "Log in",
        "Create account",
    ]
)


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

with login_tab:
    with st.form("login_form"):
        email = st.text_input(
            "Email",
        )

        password = st.text_input(
            "Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Log in",
            type="primary",
        )

        if submitted:
            user = auth_service.authenticate(
                email=email,
                password=password,
            )

            if user is None:
                st.error(
                    "Invalid email or password."
                )

            else:
                login_user(user)

                st.success(
                    "Login successful."
                )

                st.rerun()


# ---------------------------------------------------------
# SIGN UP
# ---------------------------------------------------------

with signup_tab:
    with st.form("signup_form"):
        display_name = st.text_input(
            "Your name",
        )

        signup_email = st.text_input(
            "Email",
            key="signup_email",
        )

        signup_password = st.text_input(
            "Password",
            type="password",
            key="signup_password",
        )

        signup_password_confirm = (
            st.text_input(
                "Confirm password",
                type="password",
            )
        )

        signup_submitted = (
            st.form_submit_button(
                "Create account"
            )
        )

        if signup_submitted:
            if (
                signup_password
                != signup_password_confirm
            ):
                st.error(
                    "Passwords do not match."
                )

            else:
                try:
                    user = auth_service.register(
                        email=signup_email,
                        display_name=display_name,
                        password=signup_password,
                    )

                    login_user(user)

                    st.success(
                        "Account created."
                    )

                    st.rerun()

                except ValueError as exc:
                    st.error(str(exc))


