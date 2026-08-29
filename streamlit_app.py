import streamlit as st

from services.candidate_repository import CandidateRepository
from services.session_auth import get_current_user


st.set_page_config(
    page_title="JobHunter",
    page_icon="🎯",
    layout="wide",
)


current_user = get_current_user()


if current_user is None:
    navigation = st.navigation(
        [
            st.Page(
                "pages/00_Home.py",
                title="Home",
                icon=":material/home:",
                default=True,
            ),
            st.Page(
                "pages/0_Login.py",
                title="Log in",
                icon=":material/login:",
            ),
        ]
    )

else:
    candidate = None

    if current_user.candidate_id:
        candidate = CandidateRepository().get(
            current_user.candidate_id
        )

    profile_ready = bool(
        candidate
        and candidate.professional_summary.strip()
        and candidate.current_role.strip()
    )

    if not profile_ready:
        navigation = st.navigation(
            [
                st.Page(
                    "pages/3_Profile.py",
                    title="Create your profile",
                    icon=":material/person_add:",
                    default=True,
                ),
            ]
        )

    else:
        navigation = st.navigation(
            [
                st.Page(
                    "app.py",
                    title="Dashboard",
                    icon=":material/dashboard:",
                    default=True,
                ),
                st.Page(
                    "pages/1_Opportunities.py",
                    title="Opportunities",
                    icon=":material/work:",
                ),
                st.Page(
                    "pages/2_Sources.py",
                    title="Sources",
                    icon=":material/hub:",
                ),
                st.Page(
                    "pages/3_Profile.py",
                    title="Profile",
                    icon=":material/person:",
                ),
                st.Page(
                    "pages/4_Improvements.py",
                    title="Improvements",
                    icon=":material/trending_up:",
                ),
            ]
        )


navigation.run()
