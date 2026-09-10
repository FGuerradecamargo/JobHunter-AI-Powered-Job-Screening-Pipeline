import streamlit as st

from services.account_recovery_service import (
    AccountRecoveryService,
)
from services.auth_service import AuthService
from services.email_verification_delivery_service import (
    EmailVerificationDeliveryService,
)
from services.google_account_service import (
    GoogleAccountService,
)
from services.google_identity_service import (
    GoogleIdentityService,
)
from services.session_auth import (
    get_authenticated_user,
    login_user,
    logout_user,
)


st.set_page_config(
    page_title="WorkPilot Login",
    page_icon="🔐",
)

st.title("WorkPilot")

auth_service = AuthService()

authenticated_user = get_authenticated_user()


# ---------------------------------------------------------
# GOOGLE OIDC
# ---------------------------------------------------------

if authenticated_user is None:
    if st.user.is_logged_in:
        google_claims = {
            "sub": st.user.get(
                "sub",
                "",
            ),
            "email": st.user.get(
                "email",
                "",
            ),
            "email_verified": st.user.get(
                "email_verified",
                False,
            ),
            "name": st.user.get(
                "name",
                "",
            ),
        }

        try:
            google_resolution = (
                GoogleIdentityService()
                .resolve(
                    google_claims
                )
            )

        except (
            ValueError,
            RuntimeError,
        ):
            st.error(
                "We could not verify your Google "
                "identity. Please try again."
            )

            if st.button(
                "Restart Google sign-in",
                key="restart_google_oidc",
            ):
                st.logout()

            st.stop()

        if (
            google_resolution.status
            == GoogleIdentityService.LINKED
        ):
            login_user(
                google_resolution.user
            )

            st.rerun()

        if (
            google_resolution.status
            == GoogleIdentityService
            .REGISTRATION_REQUIRED
        ):
            try:
                google_user = (
                    GoogleAccountService()
                    .register(
                        google_resolution
                    )
                )

            except Exception:
                st.error(
                    "We could not create your "
                    "WorkPilot account. "
                    "Please try again."
                )

                st.stop()

            login_user(
                google_user
            )

            st.rerun()

        if (
            google_resolution.status
            == GoogleIdentityService
            .LINK_REQUIRED
        ):
            st.success(
                "Google identity verified."
            )

            st.caption(
                f"Google account: "
                f"{google_resolution.email}"
            )

            st.write(
                "A WorkPilot account already "
                "exists with this email."
            )

            st.write(
                "Enter your WorkPilot password "
                "once to securely connect Google "
                "to your existing account."
            )

            with st.form(
                "google_account_link_form"
            ):
                link_password = st.text_input(
                    "WorkPilot password",
                    type="password",
                )

                link_submitted = (
                    st.form_submit_button(
                        "Connect Google account",
                        type="primary",
                    )
                )

            if link_submitted:
                authenticated_user = (
                    auth_service.authenticate(
                        email=(
                            google_resolution
                            .email
                        ),
                        password=link_password,
                    )
                )

                if authenticated_user is None:
                    st.error(
                        "Invalid email or password."
                    )

                else:
                    try:
                        linked_user = (
                            GoogleAccountService()
                            .link_existing_account(
                                resolution=(
                                    google_resolution
                                ),
                                authenticated_user=(
                                    authenticated_user
                                ),
                            )
                        )

                    except ValueError:
                        st.error(
                            "We could not connect "
                            "this Google account."
                        )

                    else:
                        login_user(
                            linked_user
                        )

                        st.rerun()

            if st.button(
                "Use a different Google account",
                key="change_google_account",
            ):
                st.logout()

            st.stop()

    else:
        if st.button(
            "Continue with Google",
            use_container_width=True,
            key="google_oidc_login",
        ):
            st.login("google")


# ---------------------------------------------------------
# ALREADY LOGGED IN
# ---------------------------------------------------------

if authenticated_user is not None:
    st.success(
        f"Logged in as {authenticated_user.display_name}"
    )

    st.write(
        f"Access level: {authenticated_user.access_level}"
    )

    if authenticated_user.candidate_id:
        st.write(
            f"Profile: {authenticated_user.candidate_id}"
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


    with st.expander(
        "Forgot password?"
    ):
        st.write(
            "Enter your email address and "
            "we'll send password reset "
            "instructions if the account "
            "supports password sign-in."
        )

        with st.form(
            "forgot_password_form"
        ):
            recovery_email = (
                st.text_input(
                    "Email",
                    key=(
                        "password_recovery_email"
                    ),
                )
            )

            recovery_submitted = (
                st.form_submit_button(
                    "Send reset instructions"
                )
            )

            if recovery_submitted:
                if not str(
                    recovery_email or ""
                ).strip():
                    st.error(
                        "Enter your email address."
                    )

                else:
                    response = (
                        AccountRecoveryService
                        .request_password_reset(
                            recovery_email
                        )
                    )

                    st.success(
                        response
                    )


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

                    (
                        EmailVerificationDeliveryService
                        .send_verification_email(
                            user.id
                        )
                    )

                    login_user(user)

                    st.success(
                        "Account created."
                    )

                    st.rerun()

                except ValueError as exc:
                    st.error(str(exc))
