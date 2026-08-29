import logging
import calendar
from datetime import date
from textwrap import dedent

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



def _format_month_year(value):
    if not value:
        return ""

    try:
        year, month = value.split("-")
        return f"{calendar.month_abbr[int(month)]} {year}"
    except (ValueError, AttributeError, IndexError):
        return value


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



# =========================================================
# WORKPILOT ONBOARDING V2
# =========================================================

WORKPILOT_ONBOARDING_CSS = """
<style>
    .wp-onboarding-shell {
        width: 100%;
        margin-bottom: 1.35rem;
    }

    .wp-stepper {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        width: 100%;
        margin: 0.2rem 0 1.15rem 0;
    }

    .wp-step-item {
        width: 22%;
        text-align: center;
        position: relative;
        z-index: 2;
    }

    .wp-step-circle {
        width: 46px;
        height: 46px;
        margin: 0 auto 0.6rem auto;
        border-radius: 50%;
        background: #EAF0F1;
        color: #17343B;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1rem;
        border: 1px solid #E1E8E9;
    }

    .wp-step-item.active .wp-step-circle {
        background: #075665;
        color: white;
        border-color: #075665;
    }

    .wp-step-item.done .wp-step-circle {
        background: #D9EAEB;
        color: #075665;
        border-color: #C8E0E2;
    }

    .wp-step-label {
        color: #52666B;
        font-size: 0.92rem;
        font-weight: 500;
    }

    .wp-step-item.active .wp-step-label {
        color: #123F4A;
        font-weight: 700;
    }

    .wp-progress-row {
        display: flex;
        gap: 1rem;
        align-items: center;
        margin-bottom: 1.55rem;
    }

    .wp-progress-track {
        flex: 1;
        height: 7px;
        border-radius: 99px;
        background: #E6ECEC;
        overflow: hidden;
    }

    .wp-progress-fill {
        height: 100%;
        background: #075665;
        border-radius: 99px;
    }

    .wp-progress-number {
        min-width: 42px;
        color: #53676C;
        font-size: 0.92rem;
        font-weight: 600;
    }

    .wp-side-card {
        background: #FFFFFF;
        border: 1px solid #E1E8E8;
        border-radius: 14px;
        padding: 1.45rem 1.4rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(18, 63, 74, 0.035);
    }

    .wp-side-title {
        color: #38525A;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 1.2rem;
    }

    .wp-side-step {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: #607278;
        margin: 0.9rem 0;
        font-size: 0.93rem;
    }

    .wp-side-step.active {
        color: #123F4A;
        font-weight: 700;
    }

    .wp-side-dot {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        border: 1.5px solid #9FB0B4;
        flex: 0 0 auto;
    }

    .wp-side-step.active .wp-side-dot {
        background: #075665;
        border-color: #075665;
    }

    .wp-side-step.done .wp-side-dot {
        background: #D9EAEB;
        border-color: #8DBFC4;
    }

    .wp-why-row {
        display: flex;
        gap: 0.9rem;
        align-items: flex-start;
        color: #425B62;
        font-size: 0.9rem;
        line-height: 1.55;
    }

    .wp-why-icon {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #DDF0F1;
        color: #075665;
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        font-size: 1.05rem;
    }

    .wp-private {
        display: flex;
        gap: 0.75rem;
        align-items: center;
        margin-top: 1.35rem;
        color: #607278;
        font-size: 0.85rem;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF !important;
        border: 1px solid #E1E8E8 !important;
        border-radius: 15px !important;
        box-shadow: 0 2px 14px rgba(18, 63, 74, 0.035);
    }

    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 0.35rem 0.55rem;
    }

    .stTextInput input,
    .stTextArea textarea {
        background: #FFFFFF !important;
        border-color: #D5DFE1 !important;
    }

    div[data-baseweb="select"] > div {
        background: #FFFFFF !important;
        border-color: #D5DFE1 !important;
    }

    .stButton > button[kind="primary"] {
        background: #075665 !important;
        border-color: #075665 !important;
        color: #FFFFFF !important;
        border-radius: 9px !important;
        font-weight: 650 !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: #064955 !important;
        border-color: #064955 !important;
    }

    @media (max-width: 900px) {
        .wp-step-label {
            font-size: 0.75rem;
        }

        .wp-step-circle {
            width: 38px;
            height: 38px;
        }

        .wp-side-card {
            margin-top: 0.8rem;
        }
    }

    /* -----------------------------------------------------
       STREAMLIT FORM CONTROLS
       ----------------------------------------------------- */

    .stTextInput input,
    .stTextArea textarea {
        color: #18363D !important;
        background: #FFFFFF !important;
        border-color: #CBD7D9 !important;
    }

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #8A9A9E !important;
        opacity: 1 !important;
    }

    div[data-baseweb="select"] > div {
        background: #FFFFFF !important;
        color: #18363D !important;
        border-color: #CBD7D9 !important;
        min-height: 42px;
    }

    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input {
        color: #18363D !important;
    }

    div[data-baseweb="select"] input::placeholder {
        color: #8A9A9E !important;
        opacity: 1 !important;
    }

    /* Dropdown menu rendered outside the main select */
    div[data-baseweb="popover"] {
        z-index: 999999 !important;
    }

    div[data-baseweb="popover"] > div {
        background: #FFFFFF !important;
        color: #18363D !important;
        border-radius: 10px !important;
        border: 1px solid #D6E0E2 !important;
        box-shadow: 0 8px 28px rgba(7, 62, 73, 0.14) !important;
    }

    ul[role="listbox"] {
        background: #FFFFFF !important;
        color: #18363D !important;
    }

    li[role="option"] {
        background: #FFFFFF !important;
        color: #18363D !important;
    }

    li[role="option"]:hover {
        background: #EAF4F4 !important;
        color: #075665 !important;
    }

    li[role="option"] * {
        color: inherit !important;
    }

    /* Selected language chips */
    span[data-baseweb="tag"] {
        background: #DDF0F1 !important;
        color: #075665 !important;
    }

    /* Primary CTA */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button {
        background: #075665 !important;
        border-color: #075665 !important;
        color: #FFFFFF !important;
    }

    .stButton > button[kind="primary"] *,
    .stFormSubmitButton > button * {
        color: #FFFFFF !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button:hover {
        background: #064955 !important;
        border-color: #064955 !important;
        color: #FFFFFF !important;
    }


    /* WorkPilot secondary buttons */
    .stButton > button:not([kind="primary"]) {
        background: #FFFFFF !important;
        border: 1px solid #B7C7CA !important;
        color: #123F4A !important;
        font-weight: 650 !important;
    }

    .stButton > button:not([kind="primary"]) * {
        color: #123F4A !important;
    }

    .stButton > button:not([kind="primary"]):hover {
        background: #EDF5F5 !important;
        border-color: #075665 !important;
        color: #075665 !important;
    }

    .stButton > button:not([kind="primary"]):hover * {
        color: #075665 !important;
    }

</style>
"""



def _render_workpilot_stepper(step):
    labels = [
        "About you",
        "Your experience",
        "Your direction",
        "Build profile",
    ]

    items = []

    for index, label in enumerate(labels, start=1):
        if index < step:
            state = "done"
        elif index == step:
            state = "active"
        else:
            state = ""

        items.append(
            f"""
            <div class="wp-step-item {state}">
                <div class="wp-step-circle">{index}</div>
                <div class="wp-step-label">{label}</div>
            </div>
            """
        )

    percentage = step * 25

    html = WORKPILOT_ONBOARDING_CSS + f"""
    <div class="wp-onboarding-shell">
        <div class="wp-stepper">
            {''.join(items)}
        </div>

        <div class="wp-progress-row">
            <div class="wp-progress-track">
                <div
                    class="wp-progress-fill"
                    style="width: {percentage}%"
                ></div>
            </div>

            <div class="wp-progress-number">
                {percentage}%
            </div>
        </div>
    </div>
    """

    st.html(html)


def _render_workpilot_side_panel(step):
    labels = [
        "About you",
        "Your experience",
        "Your direction",
        "Build profile",
    ]

    rows = []

    for index, label in enumerate(labels, start=1):
        if index < step:
            state = "done"
        elif index == step:
            state = "active"
        else:
            state = ""

        rows.append(
            f"""
            <div class="wp-side-step {state}">
                <span class="wp-side-dot"></span>
                <span>{label}</span>
            </div>
            """
        )

    reasons = {
        1: (
            "This helps us find better matches and show you "
            "realistic opportunities that fit your situation."
        ),
        2: (
            "Your real experience gives WorkPilot evidence of "
            "what you can already do beyond job titles."
        ),
        3: (
            "Your past should inform your next move, not decide it. "
            "This tells WorkPilot where you actually want to go."
        ),
        4: (
            "WorkPilot combines your evidence and direction into "
            "one profile used throughout your career system."
        ),
    }

    html = f"""
    <div class="wp-side-card">
        <div class="wp-side-title">
            YOUR PROGRESS
        </div>

        {''.join(rows)}
    </div>

    <div class="wp-side-card">
        <div class="wp-side-title">
            WHY WE ASK
        </div>

        <div class="wp-why-row">
            <div class="wp-why-icon">↗</div>

            <div>
                {reasons[step]}
            </div>
        </div>

        <div class="wp-private">
            <span>▣</span>
            <span>Your profile data is private.</span>
        </div>
    </div>
    """

    st.html(html)


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

    _render_workpilot_stepper(step)

    main_col, side_col = st.columns(
        [3.25, 1.15],
        gap="large",
    )

    with main_col:
        with st.container(border=True):
            # ---------------------------------------------------------
            # STEP 1 — ABOUT YOU
            # ---------------------------------------------------------

            if step == 1:
                st.subheader("ABOUT YOU")

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
                    "Continue →",
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
                st.subheader("YOUR EXPERIENCE")

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

                            period = _format_month_year(
                                experience.start_date
                            )

                            if experience.end_date:
                                period += (
                                    " → "
                                    + _format_month_year(
                                        experience.end_date
                                    )
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

                    month_options = list(
                        range(1, 13)
                    )

                    month_labels = {
                        month: calendar.month_name[month]
                        for month in month_options
                    }

                    current_year = date.today().year
                    year_options = list(
                        range(current_year, 1969, -1)
                    )

                    st.markdown("**When did you start?**")

                    start_month_col, start_year_col = st.columns(2)

                    with start_month_col:
                        start_month = st.selectbox(
                            "Start month",
                            options=month_options,
                            index=None,
                            format_func=lambda value: (
                                month_labels[value]
                            ),
                            placeholder="Month",
                            label_visibility="collapsed",
                            key=f"start_month_{candidate_id}",
                        )

                    with start_year_col:
                        start_year = st.selectbox(
                            "Start year",
                            options=year_options,
                            index=None,
                            placeholder="Year",
                            label_visibility="collapsed",
                            key=f"start_year_{candidate_id}",
                        )

                    currently_here = st.checkbox(
                        "I currently work here",
                        key=f"current_role_{candidate_id}",
                    )

                    end_month = None
                    end_year = None

                    if not currently_here:
                        st.markdown("**When did you leave?**")

                        end_month_col, end_year_col = st.columns(2)

                        with end_month_col:
                            end_month = st.selectbox(
                                "End month",
                                options=month_options,
                                index=None,
                                format_func=lambda value: (
                                    month_labels[value]
                                ),
                                placeholder="Month",
                                label_visibility="collapsed",
                                key=f"end_month_{candidate_id}",
                            )

                        with end_year_col:
                            end_year = st.selectbox(
                                "End year",
                                options=year_options,
                                index=None,
                                placeholder="Year",
                                label_visibility="collapsed",
                                key=f"end_year_{candidate_id}",
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

                    elif (
                        start_month is None
                        or start_year is None
                    ):
                        st.warning(
                            "Select the month and year you started."
                        )

                    elif (
                        not currently_here
                        and (
                            end_month is None
                            or end_year is None
                        )
                    ):
                        st.warning(
                            "Select when you left, or choose "
                            "'I currently work here'."
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
                            start_date=(
                                f"{start_year:04d}-"
                                f"{start_month:02d}"
                            ),
                            end_date=(
                                None
                                if currently_here
                                else (
                                    f"{end_year:04d}-"
                                    f"{end_month:02d}"
                                )
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
                        "Continue →",
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
                st.subheader("YOUR DIRECTION")

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
                        "Review profile →",
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

                st.subheader("BUILD YOUR PROFILE")

                st.write(
                    "Everything is ready. WorkPilot will now "
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
                            f"({_format_month_year(experience.start_date)})"
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


    with side_col:
        _render_workpilot_side_panel(step)
