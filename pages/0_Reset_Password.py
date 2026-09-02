from __future__ import annotations

import streamlit as st

from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.password_reset_service import (
    PasswordResetService,
)


_TOKEN_SESSION_KEY = (
    "_workpilot_password_reset_token"
)

_COMPLETE_SESSION_KEY = (
    "_workpilot_password_reset_complete"
)


# ---------------------------------------------------------
# CAPTURE TOKEN AND REMOVE IT FROM THE URL
# ---------------------------------------------------------

incoming_token = str(
    st.query_params.get(
        "token",
        "",
    )
    or ""
).strip()

if incoming_token:
    st.session_state[
        _TOKEN_SESSION_KEY
    ] = incoming_token

    st.session_state.pop(
        _COMPLETE_SESSION_KEY,
        None,
    )

    # Do not leave recovery secrets in the browser URL
    # longer than necessary.
    st.query_params.clear()

    st.rerun()


# ---------------------------------------------------------
# SUCCESS STATE
# ---------------------------------------------------------

if st.session_state.get(
    _COMPLETE_SESSION_KEY
):
    st.title(
        "Password updated"
    )

    st.success(
        "Your password has been changed. "
        "All previous sessions were signed out."
    )

    st.write(
        "You can now log in with your new password."
    )

    if st.button(
        "Continue to log in",
        type="primary",
    ):
        st.session_state.pop(
            _COMPLETE_SESSION_KEY,
            None,
        )

        st.switch_page(
            "pages/0_Login.py"
        )

    st.stop()


# ---------------------------------------------------------
# RESET FORM
# ---------------------------------------------------------

token = str(
    st.session_state.get(
        _TOKEN_SESSION_KEY,
        "",
    )
    or ""
).strip()


st.title(
    "Reset your password"
)

st.write(
    "Choose a new password for your "
    "WorkPilot account."
)


if not token:
    st.error(
        "This password reset link is "
        "missing, invalid, or has expired."
    )

    st.stop()


token_is_active = (
    AccountActionTokenService
    .is_token_active(
        token,
        (
            AccountActionTokenService
            .PASSWORD_RESET
        ),
    )
)

if not token_is_active:
    st.session_state.pop(
        _TOKEN_SESSION_KEY,
        None,
    )

    st.error(
        "This password reset link "
        "is invalid or has expired."
    )

    st.stop()


with st.form(
    "password_reset_form"
):
    new_password = st.text_input(
        "New password",
        type="password",
    )

    confirm_password = st.text_input(
        "Confirm new password",
        type="password",
    )

    st.caption(
        "Use at least 15 characters."
    )

    submitted = (
        st.form_submit_button(
            "Reset password",
            type="primary",
        )
    )

    if submitted:
        if (
            new_password
            != confirm_password
        ):
            st.error(
                "Passwords do not match."
            )

        else:
            try:
                reset_successful = (
                    PasswordResetService
                    .reset_password(
                        token,
                        new_password,
                    )
                )

            except ValueError as exc:
                # Password policy errors are safe
                # and useful to show to the user.
                st.error(
                    str(exc)
                )

            else:
                if not reset_successful:
                    st.session_state.pop(
                        _TOKEN_SESSION_KEY,
                        None,
                    )

                    st.error(
                        "This password reset link "
                        "is invalid or has expired."
                    )

                else:
                    st.session_state.pop(
                        _TOKEN_SESSION_KEY,
                        None,
                    )

                    st.session_state[
                        _COMPLETE_SESSION_KEY
                    ] = True

                    # Successful reset revokes all
                    # sessions, including this browser's
                    # previous authenticated session.
                    st.rerun()
