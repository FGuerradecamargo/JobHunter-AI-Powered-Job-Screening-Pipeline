from __future__ import annotations

import streamlit as st

from services.email_verification_service import (
    EmailVerificationService,
)


st.set_page_config(
    page_title="Verify email | WorkPilot",
    page_icon="??",
)

_RESULT_SESSION_KEY = (
    "_workpilot_email_verification_result"
)


st.title("Verify your email")


query_token = str(
    st.query_params.get(
        "token",
        "",
    )
    or ""
).strip()


if query_token:
    st.session_state.pop(
        _RESULT_SESSION_KEY,
        None,
    )

    verified = (
        EmailVerificationService
        .verify_email(
            query_token
        )
    )

    st.session_state[
        _RESULT_SESSION_KEY
    ] = verified

    # Remove the secret from the browser URL
    # immediately after processing.
    st.query_params.clear()

    st.rerun()


result = st.session_state.get(
    _RESULT_SESSION_KEY
)


if result is True:
    st.success(
        "Your email has been verified."
    )

    st.write(
        "Your WorkPilot account is ready."
    )

    if st.button(
        "Continue to WorkPilot",
        type="primary",
    ):
        st.session_state.pop(
            _RESULT_SESSION_KEY,
            None,
        )

        st.switch_page(
            "pages/0_Login.py"
        )

    st.stop()


if result is False:
    st.error(
        "This email verification link "
        "is invalid or has expired."
    )

    st.write(
        "Request a new verification email "
        "from WorkPilot."
    )

    st.stop()


st.info(
    "Open the verification link from "
    "your WorkPilot email."
)
