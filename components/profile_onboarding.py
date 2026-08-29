import logging

import streamlit as st

from models.candidate_onboarding import CandidateOnboarding


logger = logging.getLogger(__name__)


LANGUAGE_OPTIONS = [
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


PRIORITY_OPTIONS = [
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


def render_profile_onboarding(
    *,
    candidate_id,
    candidate_name,
    onboarding_repository,
    profile_generation_service,
):
    step_key = f"onboarding_step_{candidate_id}"

    if step_key not in st.session_state:
        st.session_state[step_key] = 1

    step = st.session_state[step_key]

    existing_onboarding = (
        onboarding_repository.get_onboarding(
            candidate_id
        )
    )

    experiences = (
        onboarding_repository.list_work_experiences(
            candidate_id
        )
    )

    st.title("Create your Career Profile")

    st.write(
        "Tell JobHunter about your experience and where "
        "you want your career to go. We will turn it into "
        "a structured Career Profile."
    )

    labels = [
        "About you",
        "Work history",
        "Career direction",
        "Build profile",
    ]

    columns = st.columns(4)

    for index, label in enumerate(
        labels,
        start=1,
    ):
        with columns[index - 1]:
            if index < step:
                st.markdown(
                    f"**✓ {index}. {label}**"
                )
            elif index == step:
                st.markdown(
                    f"**→ {index}. {label}**"
                )
            else:
                st.caption(
                    f"{index}. {label}"
                )

    st.progress(
        step / 4
    )

    st.divider()

    # ---------------------------------------------------------
    # STEP 1 — ABOUT YOU
    # ---------------------------------------------------------

    if step == 1:
        st.subheader("1. About you")

        st.write(
            "Start with the basics that affect which "
            "opportunities are realistic for you."
        )

        location = st.text_input(
            "Where are you based?",
            value=(
                existing_onboarding.location
                if existing_onboarding
                else ""
            ),
            placeholder="Example: Limerick, Ireland",
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

        saved_languages = (
            existing_onboarding.spoken_languages
            if existing_onboarding
            else []
        )

        valid_languages = [
            language
            for language in saved_languages
            if language in LANGUAGE_OPTIONS
        ]

        spoken_languages = st.multiselect(
            "Which languages do you speak?",
            options=LANGUAGE_OPTIONS,
            default=valid_languages,
        )

        if st.button(
            "Continue to work history",
            type="primary",
            use_container_width=True,
        ):
            if not location.strip():
                st.warning(
                    "Add your location before continuing."
                )
                return

            if not spoken_languages:
                st.warning(
                    "Select at least one language."
                )
                return

            onboarding = CandidateOnboarding(
                candidate_id=candidate_id,
                location=location.strip(),
                work_authorisation=(
                    work_authorisation.strip()
                ),
                spoken_languages=spoken_languages,
                desired_next_work=(
                    existing_onboarding.desired_next_work
                    if existing_onboarding
                    else ""
                ),
                enjoyed_work=(
                    existing_onboarding.enjoyed_work
                    if existing_onboarding
                    else ""
                ),
                avoid_work=(
                    existing_onboarding.avoid_work
                    if existing_onboarding
                    else ""
                ),
                development_interests=(
                    existing_onboarding.development_interests
                    if existing_onboarding
                    else ""
                ),
                career_priorities=(
                    existing_onboarding.career_priorities
                    if existing_onboarding
                    else []
                ),
            )

            onboarding_repository.save_onboarding(
                onboarding
            )

            st.session_state[step_key] = 2
            st.rerun()

    # ---------------------------------------------------------
    # STEP 2 — WORK HISTORY
    # ---------------------------------------------------------

    elif step == 2:
        st.subheader("2. Work history")

        st.write(
            "Tell us what you actually did. Do not worry "
            "about writing it like a CV."
        )

        if experiences:
            st.markdown("**Experiences added**")

            for experience in experiences:
                with st.container(border=True):
                    st.markdown(
                        f"**{experience.company}**"
                    )

                    period = experience.start_date

                    if experience.end_date:
                        period += (
                            f" → {experience.end_date}"
                        )
                    else:
                        period += " → Present"

                    st.caption(period)

                    if st.button(
                        "Remove",
                        key=(
                            "onboarding_remove_"
                            f"{experience.id}"
                        ),
                    ):
                        onboarding_repository.delete_work_experience(
                            experience.id
                        )
                        st.rerun()

            st.divider()

        with st.form(
            f"onboarding_experience_{candidate_id}"
        ):
            company = st.text_input(
                "Company"
            )

            col_start, col_end = st.columns(2)

            with col_start:
                start_date = st.text_input(
                    "When did you start?",
                    placeholder="Example: October 2021",
                )

            with col_end:
                end_date = st.text_input(
                    "When did you leave?",
                    placeholder=(
                        "Leave blank if this is your "
                        "current company"
                    ),
                )

            career_story = st.text_area(
                "Tell us your story at this company",
                placeholder=(
                    "How did you join? Which roles did "
                    "you have? Did you move teams, get "
                    "promoted or take on new responsibilities?"
                ),
                height=180,
            )

            day_to_day = st.text_area(
                "What was your day-to-day work actually like?",
                placeholder=(
                    "Imagine a friend starts this job "
                    "tomorrow. What would they actually do?"
                ),
                height=200,
            )

            add_experience = (
                st.form_submit_button(
                    "Add this experience",
                    use_container_width=True,
                )
            )

        if add_experience:
            if not company.strip():
                st.warning(
                    "Company is required."
                )

            elif not start_date.strip():
                st.warning(
                    "Start date is required."
                )

            elif not career_story.strip():
                st.warning(
                    "Tell us your story at this company."
                )

            elif not day_to_day.strip():
                st.warning(
                    "Describe your day-to-day work."
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

                st.rerun()

        st.divider()

        col_back, col_next = st.columns(2)

        with col_back:
            if st.button(
                "Back",
                use_container_width=True,
            ):
                st.session_state[step_key] = 1
                st.rerun()

        with col_next:
            if st.button(
                "Continue to career direction",
                type="primary",
                use_container_width=True,
            ):
                experiences = (
                    onboarding_repository
                    .list_work_experiences(
                        candidate_id
                    )
                )

                if not experiences:
                    st.warning(
                        "Add at least one work "
                        "experience before continuing."
                    )
                    return

                st.session_state[step_key] = 3
                st.rerun()

    # ---------------------------------------------------------
    # STEP 3 — CAREER DIRECTION
    # ---------------------------------------------------------

    elif step == 3:
        st.subheader("3. Career direction")

        st.write(
            "Your history tells us what you have done. "
            "Now tell us where you want to go."
        )

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

        career_priorities = st.multiselect(
            "What matters most in your next job?",
            options=PRIORITY_OPTIONS,
            default=(
                existing_onboarding.career_priorities
                if existing_onboarding
                else []
            ),
        )

        col_back, col_next = st.columns(2)

        with col_back:
            if st.button(
                "Back",
                use_container_width=True,
            ):
                st.session_state[step_key] = 2
                st.rerun()

        with col_next:
            if st.button(
                "Review your profile",
                type="primary",
                use_container_width=True,
            ):
                if not desired_next_work.strip():
                    st.warning(
                        "Tell us what kind of work "
                        "you would like to do next."
                    )
                    return

                onboarding = CandidateOnboarding(
                    candidate_id=candidate_id,
                    location=(
                        existing_onboarding.location
                        if existing_onboarding
                        else ""
                    ),
                    work_authorisation=(
                        existing_onboarding.work_authorisation
                        if existing_onboarding
                        else ""
                    ),
                    spoken_languages=(
                        existing_onboarding.spoken_languages
                        if existing_onboarding
                        else []
                    ),
                    desired_next_work=(
                        desired_next_work.strip()
                    ),
                    enjoyed_work=(
                        enjoyed_work.strip()
                    ),
                    avoid_work=(
                        avoid_work.strip()
                    ),
                    development_interests=(
                        development_interests.strip()
                    ),
                    career_priorities=career_priorities,
                )

                onboarding_repository.save_onboarding(
                    onboarding
                )

                st.session_state[step_key] = 4
                st.rerun()

    # ---------------------------------------------------------
    # STEP 4 — BUILD PROFILE
    # ---------------------------------------------------------

    elif step == 4:
        onboarding = (
            onboarding_repository.get_onboarding(
                candidate_id
            )
        )

        experiences = (
            onboarding_repository.list_work_experiences(
                candidate_id
            )
        )

        st.subheader("4. Build your Career Profile")

        st.write(
            "Everything is ready. JobHunter will now "
            "turn your history and career direction into "
            "a structured Career Profile."
        )

        if onboarding:
            with st.container(border=True):
                st.markdown("**About you**")
                st.write(
                    onboarding.location
                    or "Location not provided"
                )

                if onboarding.work_authorisation:
                    st.caption(
                        onboarding.work_authorisation
                    )

                if onboarding.spoken_languages:
                    st.caption(
                        ", ".join(
                            onboarding.spoken_languages
                        )
                    )

            with st.container(border=True):
                st.markdown("**Career direction**")
                st.write(
                    onboarding.desired_next_work
                    or "Not provided"
                )

                if onboarding.career_priorities:
                    st.caption(
                        "Priorities: "
                        + ", ".join(
                            onboarding.career_priorities
                        )
                    )

        with st.container(border=True):
            st.markdown("**Work history**")

            for experience in experiences:
                st.write(
                    f"• {experience.company} "
                    f"({experience.start_date})"
                )

        st.info(
            "Your professional history will be treated "
            "as evidence of what you can do — not as a "
            "limit on where your career can go."
        )

        col_back, col_generate = st.columns(
            [1, 2]
        )

        with col_back:
            if st.button(
                "Back",
                use_container_width=True,
            ):
                st.session_state[step_key] = 3
                st.rerun()

        with col_generate:
            if st.button(
                "Build my Career Profile",
                type="primary",
                use_container_width=True,
            ):
                try:
                    with st.spinner(
                        "Building your Career Profile..."
                    ):
                        profile_generation_service.generate(
                            candidate_id=candidate_id,
                            candidate_name=candidate_name,
                        )

                    st.session_state.pop(
                        step_key,
                        None,
                    )

                    st.success(
                        "Your Career Profile is ready."
                    )

                    st.rerun()

                except Exception:
                    logger.exception(
                        "Could not generate "
                        "initial Career Profile."
                    )

                    st.error(
                        "We could not build your Career "
                        "Profile. Please try again."
                    )
