import streamlit as st

from services.access_policy import AccessPolicy
from services.admin_access_audit_service import (
    AdminAccessAuditService,
)
from services.admin_access_session import AdminAccessSession
from services.admin_reauthentication_service import (
    AdminReauthenticationService,
)
from services.candidate_repository import CandidateRepository
from services.candidate_product_state_repository import (
    CandidateProductStateRepository,
)
from services.candidate_product_state_service import (
    HiredTransitionService,
)
from services.product_mode_policy import product_mode_policy
from services.session_auth import get_authenticated_user
from services.streamlit_oidc import oidc_logged_in
from services.user_context_runtime import (
    get_active_user_context,
    set_active_user,
)
from services.user_repository import UserRepository


st.set_page_config(
    page_title="WorkPilot",
    page_icon="🎯",
    layout="wide",
)


# ---------------------------------------------------------
# WORKPILOT — GLOBAL PRODUCT SHELL
# ---------------------------------------------------------

from components.workpilot_ui import apply_theme
apply_theme()


password_reset_page = st.Page(
    "pages/0_Reset_Password.py",
    title="Reset password",
    url_path="reset-password",
    visibility="hidden",
)


email_verification_page = st.Page(
    "pages/0_Verify_Email.py",
    title="Verify email",
    url_path="verify-email",
    visibility="hidden",
)


home_page = st.Page(
    "app.py",
    title="Home",
    icon=":material/home:",
    default=True,
)

login_page = st.Page(
    "pages/0_Login.py",
    title="Log in",
    icon=":material/login:",
)

public_pages = [
    home_page,
    login_page,
    password_reset_page,
    email_verification_page,
]

# A fresh browser session has no trusted in-memory identity yet.
#
# Execute the selected public page first. That page may mount the
# encrypted-cookie component and resolve an existing durable session.
# Calling get_authenticated_user() here before navigation.run() would
# allow cookie readiness to stop the shell before /Login can render.
if st.session_state.get("current_user") is None:
    st.session_state["workpilot_public_navigation"] = True
    navigation = st.navigation(
        public_pages,
        position="hidden",
    )

    if (
        oidc_logged_in()
        and navigation.url_path
        != login_page.url_path
    ):
        st.switch_page(
            login_page
        )

    navigation.run()

    # A public page may have restored a valid durable session or completed
    # login. Re-enter the shell so private navigation is built from that
    # verified identity.
    if st.session_state.get("current_user") is not None:
        st.rerun()

    st.stop()

# Never authorize the private shell from session_state alone.
# Revalidate the encrypted cookie and server-side session every run.
authenticated_user = get_authenticated_user()

google_oidc_pending = bool(
    authenticated_user is None
    and oidc_logged_in()
)


if authenticated_user is None:
    st.session_state["workpilot_public_navigation"] = True
    navigation = st.navigation(
        public_pages,
        position="hidden",
    )

    if (
        google_oidc_pending
        and navigation.url_path
        != login_page.url_path
    ):
        st.switch_page(
            login_page
        )

else:
    st.session_state["workpilot_public_navigation"] = False
    user_context = (
        get_active_user_context(
            authenticated_user=authenticated_user
        )
    )

    active_user = user_context.active_user
    admin_access_session = AdminAccessSession(
        st.session_state
    )
    admin_access_audit = AdminAccessAuditService()

    if AccessPolicy.can_view_all_users(
        authenticated_user
    ):
        authorized_target_id = (
            admin_access_session.get_authorized_target(
                authenticated_user_id=(
                    authenticated_user.id
                )
            )
        )

        if (
            active_user.id != authenticated_user.id
            and active_user.id != authorized_target_id
        ):
            set_active_user(
                authenticated_user=authenticated_user,
                active_user_id=authenticated_user.id,
            )

            st.rerun()

        st.sidebar.caption(
            "ADMIN"
        )

        st.sidebar.caption(
            "Signed in as "
            f"{authenticated_user.display_name}"
        )

        admin_access_key = (
            "admin_access_open_"
            f"{authenticated_user.id}"
        )

        if active_user.id != authenticated_user.id:
            st.sidebar.write(
                "Viewing as "
                f"**{active_user.display_name}**"
            )

            if st.sidebar.button(
                "Return to my profile",
                use_container_width=True,
                key="admin_return_to_self",
            ):
                set_active_user(
                    authenticated_user=(
                        authenticated_user
                    ),
                    active_user_id=(
                        authenticated_user.id
                    ),
                )

                admin_access_session.reset(
                    authenticated_user_id=(
                        authenticated_user.id
                    )
                )

                admin_access_audit.record_ended(
                    authenticated_user=(
                        authenticated_user
                    ),
                    previous_active_user=active_user,
                )

                st.session_state.pop(
                    admin_access_key,
                    None,
                )

                st.rerun()

        access_button_label = (
            "Change viewed profile"
            if active_user.id != authenticated_user.id
            else "Administrative access"
        )

        if st.sidebar.button(
            access_button_label,
            use_container_width=True,
            key="admin_open_access",
        ):
            st.session_state[admin_access_key] = True

        if st.session_state.get(admin_access_key):
            users = UserRepository().list_all()

            user_by_id = {
                user.id: user
                for user in users
            }

            user_by_id.setdefault(
                authenticated_user.id,
                authenticated_user,
            )

            target_ids = [
                user_id
                for user_id in user_by_id
                if user_id != authenticated_user.id
            ]

            if not target_ids:
                st.sidebar.info(
                    "No other profiles are available."
                )

            else:
                with st.sidebar.form(
                    "admin_access_form_"
                    f"{authenticated_user.id}"
                ):
                    selected_active_user_id = st.selectbox(
                        "Profile",
                        options=target_ids,
                        format_func=lambda user_id: (
                            f"{user_by_id[user_id].display_name} "
                            f"({user_by_id[user_id].email})"
                        ),
                        key=(
                            "admin_access_target_"
                            f"{authenticated_user.id}"
                        ),
                    )

                    admin_password = st.text_input(
                        "WorkPilot password",
                        type="password",
                    )

                    access_submitted = (
                        st.form_submit_button(
                            "Confirm access",
                            type="primary",
                            use_container_width=True,
                        )
                    )

            if target_ids and access_submitted:
                if (
                    AdminReauthenticationService()
                    .reauthenticate(
                        authenticated_user=(
                            authenticated_user
                        ),
                        password=admin_password,
                    )
                ):
                    target_user = user_by_id[
                        selected_active_user_id
                    ]

                    admin_access_audit.record_started(
                        authenticated_user=(
                            authenticated_user
                        ),
                        target_user=target_user,
                    )

                    admin_access_session.authorize(
                        authenticated_user_id=(
                            authenticated_user.id
                        ),
                        target_user_id=(
                            selected_active_user_id
                        ),
                    )

                    set_active_user(
                        authenticated_user=(
                            authenticated_user
                        ),
                        active_user_id=(
                            selected_active_user_id
                        ),
                    )

                    st.session_state.pop(
                        admin_access_key,
                        None,
                    )

                    st.rerun()

                else:
                    admin_access_audit.record_denied(
                        authenticated_user=(
                            authenticated_user
                        ),
                        active_user=active_user,
                        target_user_id=(
                            selected_active_user_id
                        ),
                    )

                    st.sidebar.error(
                        "Administrative access was not verified. "
                        "Use your WorkPilot password or reset it "
                        "from the login page."
                    )

    else:
        admin_access_session.reset(
            authenticated_user_id=(
                authenticated_user.id
            )
        )


    candidate = None

    if active_user.candidate_id:
        candidate = CandidateRepository().get(
            active_user.candidate_id
        )

    profile_ready = bool(
        candidate
        and candidate.professional_summary.strip()
        and candidate.current_role.strip()
    )

    product_state = (
        CandidateProductStateRepository().get(candidate.id)
        if candidate is not None
        else None
    )

    product_policy = (
        product_mode_policy(product_state)
        if product_state is not None
        else None
    )

    if not profile_ready:
        if (
            product_policy is not None
            and not product_policy.can_mutate
        ):
            navigation = st.navigation(
                [
                    st.Page(
                        "app.py",
                        title="Dashboard",
                        icon=":material/dashboard:",
                        default=True,
                    ),
                    st.Page("pages/5_Applications.py", title="Applications", url_path="Applications", icon=":material/assignment:"),
                    st.Page("pages/4_Improvements.py", title="Improvements", icon=":material/trending_up:"),
                    st.Page("pages/3_Profile.py", title="Profile", icon=":material/person:"),
                    st.Page("pages/6_Settings.py", title="Settings", url_path="Settings", icon=":material/settings:"),
                    password_reset_page,
                    email_verification_page,
                ]
            )
        else:
            navigation = st.navigation(
                [
                    st.Page(
                        "pages/3_Profile.py",
                        title="Create your profile",
                        icon=":material/person_add:",
                        default=True,
                    ),
                    password_reset_page,
                    email_verification_page,
                ]
            )

    else:
        if product_state.subscription_end_requested:
            st.sidebar.caption(
                "Subscription end requested"
            )

        if product_policy.can_return_to_search:
            st.sidebar.caption("CAREER MODE")

            if (
                active_user.id == authenticated_user.id
                and st.sidebar.button(
                    "Return to job search",
                    key="return_to_search_mode",
                    use_container_width=True,
                )
            ):
                HiredTransitionService(
                    repository=CandidateProductStateRepository(),
                ).return_to_search(
                    candidate_id=candidate.id,
                )
                st.rerun()

        elif not product_policy.can_mutate:
            st.sidebar.caption("READ-ONLY MODE")

        private_pages = [
            st.Page(
                "app.py",
                title="Dashboard",
                icon=":material/dashboard:",
                default=True,
            ),
        ]

        if product_policy.can_search:
            private_pages.append(
                st.Page(
                    "pages/1_Opportunities.py",
                    title="Jobs",
                    url_path="Jobs",
                    icon=":material/work:",
                )
            )

        if product_policy.show_sources:
            private_pages.append(
                st.Page(
                    "pages/2_Sources.py",
                    title="Sources",
                    visibility="hidden",
                    url_path="Sources",
                    icon=":material/hub:",
                )
            )

        private_pages.append(st.Page("pages/5_Applications.py", title="Applications", url_path="Applications", icon=":material/assignment:"))

        if product_policy.show_improvements:
            private_pages.append(st.Page("pages/4_Improvements.py", title="Improvements", icon=":material/trending_up:"))

        if product_policy.show_profile:
            private_pages.append(
                st.Page(
                    "pages/3_Profile.py",
                    title="Profile",
                    icon=":material/person:",
                )
            )

        else:
            private_pages.append(st.Page("pages/3_Profile.py", title="Profile", icon=":material/person:"))

        private_pages.append(st.Page("pages/6_Settings.py", title="Settings", url_path="Settings", icon=":material/settings:"))

        private_pages.extend(
            [
                password_reset_page,
                email_verification_page,
            ]
        )

        navigation = st.navigation(private_pages)


navigation.run()

