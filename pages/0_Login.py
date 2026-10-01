import streamlit as st
from services.oidc_diagnostics import oidc_call, oidc_stage
from components.public_landing import render_auth_intro, render_public_theme

from services.account_recovery_service import (
    AccountRecoveryService,
)
from services.auth_service import AuthService
from services.authentication_coordinator import (
    AuthenticationCoordinator, GoogleRegistrationError, GoogleSessionError,
)
from services.email_verification_delivery_service import (
    EmailVerificationDeliveryService,
)
from services.google_identity_service import (
    GoogleIdentityService,
)
from services.session_auth import (
    get_authenticated_user,
    get_authenticated_user_if_ready,
    login_user,
    logout_user,
)
from services.streamlit_oidc import (
    oidc_available,
    oidc_logged_in,
)


def render_authentication(authenticated_user, auth_service) -> None:
    coordinator = AuthenticationCoordinator(auth_service=auth_service)
    authentication_notice = st.session_state.pop(
        "authentication_notice",
        None,
    )
    if authentication_notice:
        st.info(authentication_notice)


    # ---------------------------------------------------------
    # GOOGLE OIDC
    # ---------------------------------------------------------

    if authenticated_user is None:
        if oidc_logged_in() and st.session_state.get("reauthentication_required"):
            st.info("Please sign in again to continue.")
            if st.button("Restart Google sign-in", key="restart_expired_google_session"):
                st.logout()
            st.stop()

        if oidc_logged_in():
            with oidc_stage("callback"):
                pass
            try:
                with oidc_stage("claims_received"):
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
                google_result = (
                    oidc_call("identity_resolution", coordinator.authenticate_with_google,
                        google_claims
                    )
                )

            except GoogleSessionError:
                st.error(
                    "We could not sign you in to WorkPilot. Please try again."
                )
                st.stop()

            except GoogleRegistrationError:
                st.error(
                    "We could not create your WorkPilot account. Please try again."
                )
                st.stop()

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

            except Exception:
                st.error(
                    "We could not verify your Google "
                    "identity. Please try again."
                )
                st.stop()

            if google_result.status in (
                GoogleIdentityService.LINKED,
                GoogleIdentityService.REGISTRATION_REQUIRED,
            ):
                st.rerun()

            google_resolution = google_result.resolution
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
                    try:
                        linked_user = oidc_call(
                            "account_link", coordinator.link_google_with_password,
                            google_resolution, link_password,
                        )
                    except ValueError:
                        st.error(
                            "We could not connect "
                            "this Google account."
                        )
                    else:
                        if linked_user is None:
                            st.error("Invalid email or password.")
                        else:
                            st.rerun()

                if st.button(
                    "Use a different Google account",
                    key="change_google_account",
                ):
                    st.logout()

                st.stop()

        else:
            if (
                oidc_available()
                and st.button(
                    "Continue with Google",
                    use_container_width=True,
                    key="google_oidc_login",
                )
            ):
                with oidc_stage("start"):
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

            if oidc_logged_in():
                st.logout()

            st.rerun()

        st.stop()


    # ---------------------------------------------------------
    # LOGIN / SIGN UP
    # ---------------------------------------------------------

    login_tab, signup_tab = st.tabs(
        [
            "Log in",
            "Create account",
        ],
        default=("Create account" if st.session_state.get("public_auth_intent") == "signup" else "Log in"),
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
                user = coordinator.authenticate_with_password(
                    email=email,
                    password=password,
                )

                if user is None:
                    st.error(
                        "Invalid email or password."
                    )

                else:
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

                    except Exception:
                        st.error(
                            "We could not create your account. "
                            "Please try again."
                        )


st.set_page_config(
    page_title="WorkPilot Login",
    page_icon="🔐",
)

auth_service = AuthService()
authenticated_user = (
    get_authenticated_user_if_ready()
)

if authenticated_user is None:
    render_public_theme()
    with st.container(key="wp-auth-layout"):
        introduction, authentication = st.columns([0.95, 1.05], gap="large")
        with introduction:
            render_auth_intro()
            if st.button("Back to Home", key="public_back_home"):
                st.switch_page("app.py")
        with authentication:
            with st.container(key="wp-auth-card"):
                st.header(
                    "Start with your career."
                    if st.session_state.get("public_auth_intent") == "signup"
                    else "Welcome back."
                )
                st.caption("Your next chapter starts here.")
                render_authentication(authenticated_user, auth_service)
else:
    st.title("WorkPilot")
    render_authentication(authenticated_user, auth_service)
