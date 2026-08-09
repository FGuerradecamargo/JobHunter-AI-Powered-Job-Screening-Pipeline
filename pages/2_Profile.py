import streamlit as st

from models.candidate_onboarding import CandidateOnboarding
from models.work_experience import WorkExperience
from services.candidate_onboarding_repository import (
    CandidateOnboardingRepository,
)
from services.user_repository import UserRepository

from services.ai.openai_client import OpenAIClient
from services.candidate_profile_generation_service import (
    CandidateProfileGenerationService,
)
from services.candidate_repository import CandidateRepository
from services.access_policy import AccessPolicy
from services.session_auth import require_login

current_user = require_login()

st.set_page_config(
    page_title="Professional Profile",
    page_icon="👤",
    layout="wide",
)

st.title("Professional Profile")

st.write(
    "Tell us about your professional history in your own words. "
    "You do not need to write it like a CV."
)

user_repository = UserRepository()
onboarding_repository = CandidateOnboardingRepository()

candidate_repository = CandidateRepository()

profile_generation_service = (
    CandidateProfileGenerationService(
        llm_client=OpenAIClient(),
        onboarding_repository=onboarding_repository,
        candidate_repository=candidate_repository,
    )
)

users = user_repository.list_all()

if not users:
    st.warning("No users found.")
    st.stop()

users = user_repository.list_all()

if AccessPolicy.can_view_all_users(
    current_user
):
    accessible_users = [
        user
        for user in users
        if user.candidate_id is not None
    ]

    selected_user = st.selectbox(
        "Profile",
        accessible_users,
        format_func=lambda user: (
            f"{user.display_name} — {user.email}"
        ),
    )

else:
    selected_user = current_user

if selected_user.candidate_id is None:
    st.warning(
        "This user does not have a candidate profile yet."
    )
    st.stop()

candidate_id = selected_user.candidate_id

if not AccessPolicy.can_access_candidate(
    current_user,
    candidate_id,
):
    st.error("Access denied.")
    st.stop()

existing_onboarding = (
    onboarding_repository.get_onboarding(
        candidate_id
    )
)

# Reset session-based fields when changing candidate/user.
session_candidate_key = "profile_candidate_id"

if (
    session_candidate_key not in st.session_state
    or st.session_state[session_candidate_key]
    != candidate_id
):
    st.session_state[session_candidate_key] = (
        candidate_id
    )

    st.session_state.languages = (
        list(existing_onboarding.spoken_languages)
        if existing_onboarding
        else []
    )


# ---------------------------------------------------------
# ABOUT YOU
# ---------------------------------------------------------

st.divider()

st.subheader("About you")

location = st.text_input(
    "Where are you based?",
    value=(
        existing_onboarding.location
        if existing_onboarding
        else ""
    ),
)

work_authorisation = st.text_input(
    "Where are you legally allowed to work?",
    value=(
        existing_onboarding.work_authorisation
        if existing_onboarding
        else ""
    ),
    placeholder=(
        "Example: Ireland and EU without sponsorship"
    ),
)


# ---------------------------------------------------------
# LANGUAGES
# ---------------------------------------------------------

st.markdown("### Languages")

language_options = [
    "English",
    "Portuguese",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Dutch",
    "Polish",
    "Romanian",
    "Russian",
    "Ukrainian",
    "Arabic",
    "Mandarin Chinese",
    "Cantonese",
    "Japanese",
    "Korean",
    "Hindi",
    "Urdu",
    "Turkish",
    "Greek",
    "Swedish",
    "Norwegian",
    "Danish",
    "Finnish",
    "Czech",
    "Slovak",
    "Hungarian",
    "Bulgarian",
    "Croatian",
    "Serbian",
]

saved_languages = (
    existing_onboarding.spoken_languages
    if existing_onboarding
    else []
)

valid_saved_languages = [
    language
    for language in saved_languages
    if language in language_options
]

spoken_languages = st.multiselect(
    "Which languages do you speak?",
    options=language_options,
    default=valid_saved_languages,
    placeholder="Select one or more languages",
)


if st.session_state.languages:
    for index, language in enumerate(
        st.session_state.languages
    ):
        col_language_name, col_remove = (
            st.columns([5, 1])
        )

        with col_language_name:
            st.write(
                f"• {language}"
            )

        with col_remove:
            if st.button(
                "Remove",
                key=(
                    f"remove_language_{index}"
                ),
                use_container_width=True,
            ):
                st.session_state.languages.pop(
                    index
                )

                st.rerun()

else:
    st.caption(
        "No languages added yet."
    )


# ---------------------------------------------------------
# PROFESSIONAL DIRECTION
# ---------------------------------------------------------

st.divider()

st.subheader("Professional direction")

desired_next_work = st.text_area(
    "What kind of work would you like to do next?",
    value=(
        existing_onboarding.desired_next_work
        if existing_onboarding
        else ""
    ),
    height=120,
)

enjoyed_work = st.text_area(
    "What parts of your previous jobs did you enjoy most?",
    value=(
        existing_onboarding.enjoyed_work
        if existing_onboarding
        else ""
    ),
    height=120,
)

avoid_work = st.text_area(
    "What would you prefer not to do again?",
    value=(
        existing_onboarding.avoid_work
        if existing_onboarding
        else ""
    ),
    height=120,
)

development_interests = st.text_area(
    "What would you like to learn or do more of?",
    value=(
        existing_onboarding.development_interests
        if existing_onboarding
        else ""
    ),
    height=120,
)

priority_options = [
    "Salary",
    "Career growth",
    "Learning",
    "Stability",
    "Flexibility",
    "Remote work",
    "Leadership",
    "Purpose / meaningful work",
    "Work-life balance",
]

career_priorities = st.multiselect(
    "What matters most in your next job?",
    priority_options,
    default=(
        existing_onboarding.career_priorities
        if existing_onboarding
        else []
    ),
)


# ---------------------------------------------------------
# SAVE GENERAL PROFILE
# ---------------------------------------------------------

if st.button(
    "Save profile information",
    type="primary",
):
    onboarding = CandidateOnboarding(
        candidate_id=candidate_id,
        location=location.strip(),
        work_authorisation=(
            work_authorisation.strip()
        ),
        spoken_languages=spoken_languages,
        desired_next_work=(
            desired_next_work.strip()
        ),
        enjoyed_work=enjoyed_work.strip(),
        avoid_work=avoid_work.strip(),
        development_interests=(
            development_interests.strip()
        ),
        career_priorities=career_priorities,
    )

    onboarding_repository.save_onboarding(
        onboarding
    )

    st.success(
        "Profile information saved."
    )


# ---------------------------------------------------------
# WORK HISTORY
# ---------------------------------------------------------

st.divider()

st.subheader("Your work history")

st.write(
    "Add each company you worked for. "
    "Tell the story naturally — the system will "
    "structure it later."
)

with st.form(
    "add_work_experience"
):
    company = st.text_input(
        "Company"
    )

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.text_input(
            "When did you start?",
            placeholder=(
                "Example: October 2021"
            ),
        )

    with col2:
        end_date = st.text_input(
            "When did you leave?",
            placeholder=(
                "Example: August 2024 "
                "or leave blank if current"
            ),
        )

    career_story = st.text_area(
        "Tell us your story at this company",
        placeholder=(
            "Example: I joined the company in "
            "2021 as Seller Support, where I "
            "helped sellers with orders, payments "
            "and account issues. Later I moved "
            "into Fraud Operations, where I "
            "started investigating fraud, "
            "chargebacks and more complex cases..."
        ),
        height=180,
    )

    st.caption(
        "Tell us how you joined, which roles "
        "you had, how your responsibilities "
        "changed, promotions or moves between "
        "teams, and what you learned."
    )

    day_to_day = st.text_area(
        "Explain what your day-to-day work was actually like",
        placeholder=(
            "Imagine a friend is starting your job "
            "tomorrow. Explain the day from beginning "
            "to end: meetings, queues, systems, reports, "
            "investigations, people you worked with, "
            "decisions you made and problems you solved."
        ),
        height=220,
    )

    st.caption(
        "Do not write this like a CV. "
        "Describe what really happened during "
        "a normal working day."
    )

    submitted = st.form_submit_button(
        "Add experience"
    )

    if submitted:
        if not company.strip():
            st.error(
                "Company is required."
            )

        elif not start_date.strip():
            st.error(
                "Start date is required."
            )

        elif not career_story.strip():
            st.error(
                "Please tell us your story "
                "at this company."
            )

        elif not day_to_day.strip():
            st.error(
                "Please describe your "
                "day-to-day work."
            )

        else:
            onboarding_repository.add_work_experience(
                candidate_id=candidate_id,
                company=company.strip(),
                start_date=start_date.strip(),
                end_date=(
                    end_date.strip()
                    if end_date.strip()
                    else None
                ),
                career_story=(
                    career_story.strip()
                ),
                day_to_day_narrative=(
                    day_to_day.strip()
                ),
            )

            st.success(
                f"{company} added to "
                "your work history."
            )

            st.rerun()


# ---------------------------------------------------------
# SAVED EXPERIENCES
# ---------------------------------------------------------

experiences = (
    onboarding_repository.list_work_experiences(
        candidate_id
    )
)

if experiences:
    st.divider()

    st.subheader(
        "Saved experiences"
    )

    for experience in experiences:
        with st.expander(
            f"{experience.company} "
            f"— {experience.start_date}"
        ):
            edit_company = st.text_input(
                "Company",
                value=experience.company,
                key=(
                    f"company_{experience.id}"
                ),
            )

            col1, col2 = st.columns(2)

            with col1:
                edit_start_date = st.text_input(
                    "Start date",
                    value=experience.start_date,
                    key=(
                        f"start_{experience.id}"
                    ),
                )

            with col2:
                edit_end_date = st.text_input(
                    "End date",
                    value=(
                        experience.end_date or ""
                    ),
                    key=(
                        f"end_{experience.id}"
                    ),
                )

            edit_career_story = st.text_area(
                "Career story",
                value=(
                    experience.career_story
                ),
                height=180,
                key=(
                    f"career_{experience.id}"
                ),
            )

            edit_day_to_day = st.text_area(
                "Day-to-day",
                value=(
                    experience.day_to_day_narrative
                ),
                height=220,
                key=(
                    f"day_{experience.id}"
                ),
            )

            col_save, col_delete = (
                st.columns(2)
            )

            with col_save:
                if st.button(
                    "Save changes",
                    key=(
                        f"save_{experience.id}"
                    ),
                    use_container_width=True,
                ):
                    updated_experience = (
                        WorkExperience(
                            id=experience.id,
                            candidate_id=(
                                experience.candidate_id
                            ),
                            company=(
                                edit_company.strip()
                            ),
                            start_date=(
                                edit_start_date.strip()
                            ),
                            end_date=(
                                edit_end_date.strip()
                                if edit_end_date.strip()
                                else None
                            ),
                            career_story=(
                                edit_career_story.strip()
                            ),
                            day_to_day_narrative=(
                                edit_day_to_day.strip()
                            ),
                        )
                    )

                    onboarding_repository.update_work_experience(
                        updated_experience
                    )

                    st.success(
                        "Experience updated."
                    )

                    st.rerun()

            with col_delete:
                if st.button(
                    "Delete experience",
                    key=(
                        f"delete_{experience.id}"
                    ),
                    use_container_width=True,
                ):
                    onboarding_repository.delete_work_experience(
                        experience.id
                    )

                    st.success(
                        "Experience deleted."
                    )

                    st.rerun()

# ---------------------------------------------------------
# GENERATE PROFESSIONAL PROFILE
# ---------------------------------------------------------

st.divider()

st.subheader("Generate professional profile")

st.write(
    "When you are ready, JobHunter will analyse your "
    "professional history and build a structured profile "
    "based only on the experience you provided."
)

if st.button(
    "Generate professional profile",
    type="primary",
    use_container_width=True,
):
    try:
        with st.spinner(
            "Analysing your professional history..."
        ):
            candidate = (
                profile_generation_service.generate(
                    candidate_id=candidate_id,
                    candidate_name=(
                        selected_user.display_name
                    ),
                )
            )

        st.success(
            "Professional profile generated."
        )

        st.rerun()

    except Exception as exc:
        st.error(
            f"Could not generate profile: {exc}"
        )

generated_candidate = (
    candidate_repository.get(
        candidate_id
    )
)

if generated_candidate is not None:
    st.divider()

    st.subheader(
        "Your professional profile"
    )

    col_role, col_level = st.columns(2)

    with col_role:
        st.markdown("**Professional positioning**")
        st.write(
            generated_candidate.current_role
        )

    with col_level:
        st.markdown("**Current level**")
        st.write(
            generated_candidate.current_level
        )

    st.markdown(
        "**Professional summary**"
    )

    st.write(
        generated_candidate.professional_summary
    )

    if generated_candidate.target_roles:
        st.markdown(
            "**Roles that may fit your direction**"
        )

        for role in (
            generated_candidate.target_roles
        ):
            st.write(
                f"• {role}"
            )

    if generated_candidate.skills:
        st.markdown(
            "**Skills identified from your experience**"
        )

        for skill in (
            generated_candidate.skills
        ):
            st.write(
                f"• {skill}"
            )

    if generated_candidate.strengths:
        st.markdown(
            "**Professional strengths**"
        )

        for strength in (
            generated_candidate.strengths
        ):
            st.write(
                f"• {strength}"
            )

    if generated_candidate.development_areas:
        st.markdown(
            "**Development areas**"
        )

        for area in (
            generated_candidate.development_areas
        ):
            st.write(
                f"• {area}"
            )

    if generated_candidate.spoken_languages:
        st.markdown(
            "**Languages**"
        )

        st.write(
            ", ".join(
                generated_candidate.spoken_languages
            )
        )
