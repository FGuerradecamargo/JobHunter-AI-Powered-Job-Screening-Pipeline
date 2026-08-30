import logging
import streamlit as st

logger = logging.getLogger(__name__)

from models.candidate_onboarding import CandidateOnboarding
from models.work_experience import WorkExperience
from models.candidate_priority import CandidatePriority
from models.career_update import CareerUpdate
from services.candidate_onboarding_repository import (
    CandidateOnboardingRepository,
)
from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.user_repository import UserRepository

from services.ai.openai_client import OpenAIClient
from services.candidate_profile_generation_service import (
    CandidateProfileGenerationService,
)
from services.candidate_repository import CandidateRepository
from models.career_objective import CareerObjective
from services.career_objective_repository import CareerObjectiveRepository
from services.access_policy import AccessPolicy
from services.session_auth import require_login, render_logout_button
from components.profile_onboarding import render_profile_onboarding

current_user = require_login()
render_logout_button()

st.set_page_config(
    page_title="Professional Profile",
    page_icon="\U0001F464",
    layout="wide",
)

st.caption("YOUR CAREER")
st.title("Professional Profile")

st.write(
    "Your career profile brings together your experience, "
    "direction, strengths and professional evidence."
)

user_repository = UserRepository()
onboarding_repository = CandidateOnboardingRepository()

candidate_repository = CandidateRepository()
career_update_repository = CareerUpdateRepository()
career_objective_repository = CareerObjectiveRepository()

profile_generation_service = (
    CandidateProfileGenerationService(
        llm_client=OpenAIClient(),
        onboarding_repository=onboarding_repository,
        candidate_repository=candidate_repository,
        career_update_repository=career_update_repository,
    )
)

users = user_repository.list_all()

if not users:
    st.warning("No users found.")
    st.stop()

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
            f"{user.display_name} - {user.email}"
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

generated_candidate = candidate_repository.get(
    candidate_id
)

profile_ready = bool(
    generated_candidate
    and generated_candidate.professional_summary.strip()
    and generated_candidate.current_role.strip()
)

if not profile_ready:
    render_profile_onboarding(
        candidate_id=candidate_id,
        candidate_name=current_user.display_name,
        onboarding_repository=onboarding_repository,
        profile_generation_service=profile_generation_service,
    )
    st.stop()


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




# PROFILE V3.1 - PROGRESSIVE DISCLOSURE

overview_tab, direction_tab, experience_tab, details_tab = (
    st.tabs(
        [
            "Overview",
            "Direction",
            "Experience",
            "Profile details",
        ]
    )
)

with experience_tab:
    with st.expander("Personal details", expanded=False):
        # ---------------------------------------------------------
        # ABOUT YOU
        # ---------------------------------------------------------


        st.markdown("### Personal details")

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



    with st.expander("Languages", expanded=False):
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
                        f"- {language}"
                    )

                with col_remove:
                    if st.button(
                        "Remove",
                        key=(
                            f"- {language}"
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




    with st.expander("＋ Add experience", expanded=False):
        # ---------------------------------------------------------
        # WORK HISTORY
        # ---------------------------------------------------------


        st.markdown("### Add experience")

        st.write(
            "Add each company you worked for. "
            "Tell the story naturally - the system will "
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

        st.subheader(
            "Work history"
        )

        for experience in experiences:
            with st.expander(
                f"{experience.company} "
                f"- {experience.start_date}"
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


with direction_tab:
    with st.expander("Career preferences", expanded=False):
        # ---------------------------------------------------------
        # PROFESSIONAL DIRECTION
        # ---------------------------------------------------------


        st.markdown("### Career preferences")

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




    with st.expander("Career objective", expanded=False):
        # ---------------------------------------------------------
        # CURRENT CAREER OBJECTIVE
        # ---------------------------------------------------------


        st.markdown("### Career objective")

        st.write(
            "Tell WorkPilot where you want your career to move next. "
            "Your professional history remains evidence, while this "
            "objective determines which opportunities and development "
            "paths are relevant now."
        )

        active_objective = (
            career_objective_repository.get_active(
                candidate_id
            )
        )

        objective_title = st.text_input(
            "Objective title",
            value=(
                active_objective.title
                if active_objective
                else ""
            ),
            placeholder=(
                "e.g. Technical and Process Operations"
            ),
            key=f"career_objective_title_{candidate_id}",
        )

        objective_description = st.text_area(
            "Describe your career direction",
            value=(
                active_objective.description
                if active_objective
                else ""
            ),
            placeholder=(
                "Describe the kinds of roles, work and progression "
                "you want WorkPilot to prioritize."
            ),
            height=140,
            key=f"career_objective_description_{candidate_id}",
        )

        if st.button(
            (
                "Update career objective"
                if active_objective
                else "Save career objective"
            ),
            type="primary",
            use_container_width=True,
            key=f"save_career_objective_{candidate_id}",
        ):
            cleaned_title = objective_title.strip()
            cleaned_description = (
                objective_description.strip()
            )

            if not cleaned_title:
                st.warning(
                    "Add a title for your career objective."
                )

            elif not cleaned_description:
                st.warning(
                    "Describe your career direction before saving."
                )

            elif generated_candidate is None:
                st.warning(
                    "Generate your professional profile before "
                    "creating a career objective."
                )

            else:
                import uuid

                objective = CareerObjective(
                    id=(
                        active_objective.id
                        if active_objective
                        else (
                            "career_objective_"
                            + uuid.uuid4().hex
                        )
                    ),
                    candidate_id=candidate_id,
                    title=cleaned_title,
                    description=cleaned_description,
                    active=True,
                    desired_role_families=(
                        list(
                            active_objective
                            .desired_role_families
                        )
                        if active_objective
                        else []
                    ),
                    created_at=(
                        active_objective.created_at
                        if active_objective
                        else ""
                    ),
                )

                try:
                    with st.spinner(
                        "Updating your career direction..."
                    ):
                        career_objective_repository.save(
                            objective
                        )

                    st.success(
                        "Career objective updated."
                    )

                    st.rerun()

                except Exception:
                    logger.exception(
                        "Could not update career objective."
                    )
                    st.error(
                        "Could not update career objective. "
                        "Please try again."
                    )




    with st.expander("Current priorities", expanded=False):
        # ---------------------------------------------------------
        # CURRENT PRIORITIES
        # ---------------------------------------------------------


        st.markdown("### Current priorities")

        st.write(
            "Tell WorkPilot what matters particularly to you right now. "
            "Priorities influence job recommendations without changing "
            "your professional history."
        )

        st.caption(
            "Positive priorities make matching jobs more attractive. "
            "Negative priorities flag trade-offs that you may want to review."
        )

        priority_candidate = generated_candidate

        if priority_candidate is not None:
            priority_text = st.text_input(
                "Add a priority",
                placeholder=(
                    "e.g. Move to Cork, avoid weekend work, "
                    "find a more technical role..."
                ),
                key="new_priority_text",
            )

            priority_direction = st.selectbox(
                "How should WorkPilot interpret it?",
                options=[
                    "positive",
                    "negative",
                ],
                format_func=lambda value: (
                    "Positive - I want more of this"
                    if value == "positive"
                    else "Negative - I want to avoid this"
                ),
                key="new_priority_direction",
            )

            if st.button(
                "Add priority",
                use_container_width=True,
            ):
                cleaned_priority = priority_text.strip()

                if not cleaned_priority:
                    st.warning(
                        "Write a priority before adding it."
                    )

                else:
                    priority_candidate.priorities.append(
                        CandidatePriority(
                            text=cleaned_priority,
                            direction=priority_direction,
                            active=True,
                        )
                    )

                    candidate_repository.save(
                        priority_candidate
                    )

                    st.success(
                        "Priority added."
                    )

                    st.rerun()

            if priority_candidate.priorities:
                st.markdown("**Your priorities**")

                for index, priority in enumerate(
                    priority_candidate.priorities
                ):
                    with st.container(border=True):
                        priority_edit_text = st.text_input(
                            "Priority",
                            value=priority.text,
                            key=(
                                f"priority_text_"
                                f"{candidate_id}_{index}"
                            ),
                        )

                        priority_edit_direction = st.selectbox(
                            "Direction",
                            options=[
                                "positive",
                                "negative",
                            ],
                            index=(
                                0
                                if priority.direction == "positive"
                                else 1
                            ),
                            format_func=lambda value: (
                                "Positive"
                                if value == "positive"
                                else "Negative"
                            ),
                            key=(
                                f"priority_direction_"
                                f"{candidate_id}_{index}"
                            ),
                        )

                        priority_active = st.checkbox(
                            "Active",
                            value=priority.active,
                            key=(
                                f"priority_active_"
                                f"{candidate_id}_{index}"
                            ),
                        )

                        col_update, col_remove = (
                            st.columns(2)
                        )

                        with col_update:
                            if st.button(
                                "Save changes",
                                key=(
                                    f"save_priority_"
                                    f"{candidate_id}_{index}"
                                ),
                                use_container_width=True,
                            ):
                                cleaned_text = (
                                    priority_edit_text.strip()
                                )

                                if not cleaned_text:
                                    st.warning(
                                        "Priority cannot be empty."
                                    )

                                else:
                                    priority_candidate.priorities[
                                        index
                                    ] = CandidatePriority(
                                        text=cleaned_text,
                                        direction=(
                                            priority_edit_direction
                                        ),
                                        active=priority_active,
                                    )

                                    candidate_repository.save(
                                        priority_candidate
                                    )

                                    st.success(
                                        "Priority updated."
                                    )

                                    st.rerun()

                        with col_remove:
                            if st.button(
                                "Remove",
                                key=(
                                    f"remove_priority_"
                                    f"{candidate_id}_{index}"
                                ),
                                use_container_width=True,
                            ):
                                priority_candidate.priorities.pop(
                                    index
                                )

                                candidate_repository.save(
                                    priority_candidate
                                )

                                st.success(
                                    "Priority removed."
                                )

                                st.rerun()

            else:
                st.info(
                    "No current priorities added yet."
                )



with overview_tab:
    if generated_candidate is not None:
        st.divider()

        st.subheader(
            "Your positioning"
        )

        col_role, col_level = st.columns(2)

        with col_role:
            st.markdown(
                "**Professional positioning**"
            )
            st.write(
                generated_candidate.current_role
            )

        with col_level:
            st.markdown(
                "**Current level**"
            )
            st.write(
                generated_candidate.current_level
            )

        st.markdown(
            "**Professional summary**"
        )
        st.write(
            generated_candidate.professional_summary
        )

        st.divider()

        st.markdown(
            "### Career positioning"
        )

        col_current, col_bridge, col_target = (
            st.columns(3)
        )

        with col_current:
            st.markdown(
                "**Competitive now**"
            )

            if (
                generated_candidate
                .competitive_role_families
            ):
                for role in (
                    generated_candidate
                    .competitive_role_families
                ):
                    st.write(f"- {role}")
            else:
                st.caption(
                    "Not identified yet."
                )

        with col_bridge:
            st.markdown(
                "**Bridge opportunities**"
            )

            if (
                generated_candidate
                .bridge_role_families
            ):
                for role in (
                    generated_candidate
                    .bridge_role_families
                ):
                    st.write(f"- {role}")
            else:
                st.caption(
                    "Not identified yet."
                )

        with col_target:
            st.markdown(
                "**Target direction**"
            )

            if (
                generated_candidate
                .target_role_families
            ):
                for role in (
                    generated_candidate
                    .target_role_families
                ):
                    st.write(f"- {role}")
            else:
                st.caption(
                    "Not identified yet."
                )


with details_tab:
    with st.expander("Add a professional update", expanded=False):
        # PROFESSIONAL PROFILE GENERATION / UPDATE
        # ---------------------------------------------------------


        profile_exists = (
            generated_candidate is not None
        )

        if not profile_exists:
            st.subheader(
                "Generate your professional profile"
            )

            st.write(
                "This creates your initial Master Career Profile "
                "from the professional history, goals and information "
                "you provided above."
            )

            st.caption(
                "You normally only need to generate your profile once. "
                "After that, WorkPilot will keep it updated as your "
                "professional life changes."
            )

            profile_button_label = (
                "Generate professional profile"
            )

            spinner_message = (
                "Building your professional profile..."
            )

            success_message = (
                "Professional profile generated."
            )

        else:
            st.subheader(
                "Add a professional update"
            )

            st.write(
                "Add only what changed. WorkPilot keeps it as "
                "new professional evidence and considers it when "
                "evaluating future opportunities."
            )

            career_update_type = st.selectbox(
                "What changed?",
                options=[
                    "promotion",
                    "new_job",
                    "job_ended",
                    "course_or_certification",
                    "new_skill",
                    "new_responsibility",
                    "project",
                    "career_goal_change",
                    "other",
                ],
                format_func=lambda value: {
                    "promotion": "Promotion",
                    "new_job": "New job",
                    "job_ended": "Job ended or lost",
                    "course_or_certification": "Course or certification",
                    "new_skill": "New skill",
                    "new_responsibility": "New responsibility",
                    "project": "Relevant project",
                    "career_goal_change": "Career goal changed",
                    "other": "Other professional change",
                }[value],
                key=f"career_update_type_{candidate_id}",
            )

            career_update_description = st.text_area(
                "Describe what changed",
                placeholder=(
                    "Example: I completed an SQL course and now "
                    "use joins and basic queries confidently."
                ),
                key=f"career_update_description_{candidate_id}",
            )

            profile_button_label = (
                "Save professional change"
            )

        if st.button(
            profile_button_label,
            type="primary",
            use_container_width=True,
        ):
            if profile_exists:
                cleaned_update = (
                    career_update_description.strip()
                )

                if not cleaned_update:
                    st.warning(
                        "Describe what changed before updating "
                        "your professional profile."
                    )
                    st.stop()

                import uuid

                try:
                    career_update_repository.save(
                        CareerUpdate(
                            id=(
                                "career_update_"
                                + uuid.uuid4().hex
                            ),
                            candidate_id=candidate_id,
                            update_type=career_update_type,
                            description=cleaned_update,
                        )
                    )

                    st.success(
                        "Professional change saved."
                    )

                    st.rerun()

                except Exception:
                    logger.exception(
                        "Could not save professional change."
                    )
                    st.error(
                        "Could not save professional change. "
                        "Please try again."
                    )

            else:
                try:
                    with st.spinner(
                        spinner_message
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
                        success_message
                    )

                    st.rerun()

                except Exception:
                    logger.exception(
                        "Could not generate profile."
                    )
                    st.error(
                        "Could not generate profile. "
                        "Please try again."
                    )



    if generated_candidate is not None:
        with st.expander("Capabilities & strengths", expanded=False):
            st.divider()

            st.markdown(
                "### Capabilities & strengths"
            )

            col_proven, col_transferable = (
                st.columns(2)
            )

            with col_proven:
                st.markdown(
                    "**Proven capabilities**"
                )

                for capability in (
                    generated_candidate
                    .proven_capabilities
                ):
                    st.write(
                        f"- {capability}"
                    )

            with col_transferable:
                st.markdown(
                    "**Transferable capabilities**"
                )

                for capability in (
                    generated_candidate
                    .transferable_capabilities
                ):
                    st.write(
                        f"- {capability}"
                    )

            if (
                generated_candidate
                .developing_capabilities
            ):
                st.markdown(
                    "**Currently developing**"
                )

                for capability in (
                    generated_candidate
                    .developing_capabilities
                ):
                    st.write(
                        f"- {capability}"
                    )

            if generated_candidate.strengths:
                st.markdown(
                    "**Professional strengths**"
                )

                for strength in (
                    generated_candidate.strengths
                ):
                    st.write(
                        f"- {strength}"
                    )


        with st.expander("Tools & domain experience", expanded=False):
            st.divider()

            col_tools, col_domains = st.columns(2)

            with col_tools:
                st.markdown(
                    "**Tools & technologies**"
                )

                if generated_candidate.technical_tools:
                    for tool in (
                        generated_candidate
                        .technical_tools
                    ):
                        st.write(
                            f"- {tool}"
                        )
                else:
                    st.caption(
                        "No tools identified yet."
                    )

            with col_domains:
                st.markdown(
                    "**Domain experience**"
                )

                if generated_candidate.domain_experience:
                    for domain in (
                        generated_candidate
                        .domain_experience
                    ):
                        st.write(
                            f"- {domain}"
                        )
                else:
                    st.caption(
                        "No domains identified yet."
                    )


        if (
            generated_candidate
            .professional_experiences
        ):
            st.divider()

            st.markdown(
                "### Professional evidence"
            )

            st.caption(
                "How your work history supports "
                "the profile above."
            )

            for experience in (
                generated_candidate
                .professional_experiences
            ):
                role_label = (
                    experience.stated_role
                    or experience.inferred_role
                    or "Professional experience"
                )

                expander_title = (
                    f"{experience.company} ? "
                    f"{role_label}"
                )

                with st.expander(
                    expander_title
                ):
                    if experience.inferred_role:
                        st.markdown(
                            "**Functional role**"
                        )
                        st.write(
                            experience.inferred_role
                        )

                    if experience.role_family:
                        st.markdown(
                            "**Role family**"
                        )
                        st.write(
                            experience.role_family
                        )

                    if experience.summary:
                        st.markdown(
                            "**What you did**"
                        )
                        st.write(
                            experience.summary
                        )

                    if (
                        experience
                        .demonstrated_capabilities
                    ):
                        st.markdown(
                            "**Capabilities demonstrated**"
                        )

                        for capability in (
                            experience
                            .demonstrated_capabilities
                        ):
                            st.write(
                                f"- {capability}"
                            )

                    if experience.evidence:
                        st.markdown(
                            "**Evidence**"
                        )

                        for evidence in (
                            experience.evidence
                        ):
                            st.write(
                                f"- {evidence}"
                            )

        if generated_candidate.spoken_languages:
            st.divider()

            st.markdown(
                "**Languages**"
            )

            st.write(
                ", ".join(
                    generated_candidate
                    .spoken_languages
                )
            )




