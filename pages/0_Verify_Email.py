from __future__ import annotations

import streamlit as st

from services.candidate_repository import (
    CandidateRepository,
)
from services.email_verification_delivery_service import (
    EmailVerificationDeliveryService,
)
from services.email_verification_service import (
    EmailVerificationService,
)
from services.session_auth import (
    get_current_user,
)


st.set_page_config(
    page_title="Verify email | WorkPilot",
    page_icon="??",
)

_RESULT_SESSION_KEY = (
    "_workpilot_email_verification_result"
)


st.title("Verify your email")


current_user = get_current_user()


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

        if current_user is None:
            st.switch_page(
                "pages/0_Login.py"
            )

        candidate = None

        if current_user.candidate_id:
            candidate = (
                CandidateRepository()
                .get(
                    current_user.candidate_id
                )
            )

        profile_ready = bool(
            candidate
            and candidate.professional_summary.strip()
            and candidate.current_role.strip()
        )

        if profile_ready:
            st.switch_page(
                "app.py"
            )

        st.switch_page(
            "pages/3_Profile.py"
        )

    st.stop()


if (
    current_user is not None
    and EmailVerificationService
    .is_email_verified(
        current_user.id
    )
):
    st.success(
        "Your email is already verified."
    )

    st.write(
        "Your WorkPilot account is ready."
    )

    if st.button(
        "Continue to WorkPilot",
        type="primary",
        key="continue_verified_account",
    ):
        candidate = None

        if current_user.candidate_id:
            candidate = (
                CandidateRepository()
                .get(
                    current_user.candidate_id
                )
            )

        profile_ready = bool(
            candidate
            and candidate.professional_summary.strip()
            and candidate.current_role.strip()
        )

        if profile_ready:
            st.switch_page(
                "app.py"
            )

        st.switch_page(
            "pages/3_Profile.py"
        )

    st.stop()


if result is False:
    st.error(
        "This email verification link "
        "is invalid or has expired."
    )

    if current_user is not None:
        st.write(
            "You can send a new verification "
            "email to your account."
        )

        if st.button(
            "Resend verification email",
            type="primary",
        ):
            sent = (
                EmailVerificationDeliveryService
                .resend_verification_email(
                    current_user.id
                )
            )

            if sent:
                st.success(
                    "If your account still needs "
                    "verification, a new email "
                    "has been sent."
                )
            else:
                st.error(
                    "We could not send a new "
                    "verification email. "
                    "Please try again later."
                )

    else:
        st.write(
            "Log in to WorkPilot, then return "
            "here to request a new "
            "verification email."
        )

    st.stop()


st.info(
    "Open the verification link from "
    "your WorkPilot email."
)

if current_user is not None:
    if st.button(
        "Resend verification email",
    ):
        sent = (
            EmailVerificationDeliveryService
            .resend_verification_email(
                current_user.id
            )
        )

        if sent:
            st.success(
                "If your account still needs "
                "verification, a new email "
                "has been sent."
            )
        else:
            st.error(
                "We could not send a new "
                "verification email. "
                "Please try again later."
            )
