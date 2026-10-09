import calendar
from dataclasses import replace
from datetime import date

import streamlit as st

from models.candidate_onboarding import CandidateOnboarding
from components.voice_text_input import VoiceTextInputs, bind_scope
from services.onboarding_events import OnboardingEventRepository
from services.access_policy import AccessPolicy
from models.company_interview import V4_VERSION
from components.country_names import COUNTRY_NAMES


QUALIFICATION_OPTIONS = (
    "Secondary school diploma",
    "Certificate",
    "Diploma",
    "Associate degree",
    "Bachelor's degree",
    "Master's degree",
    "Doctorate",
    "Other",
)


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


# =========================================================
# WORKPILOT RAW ONBOARDING V4
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
        width: 19%;
        min-width: 0;
        overflow-wrap: anywhere;
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
        border-radius: 8px;
        padding: 1.45rem 1.4rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(18, 63, 74, 0.035);
    }

    .wp-side-title {
        color: #38525A;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0;
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
        border-radius: 8px !important;
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
        border-radius: 6px !important;
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
        border-radius: 6px !important;
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
        "About You",
        "Experience",
        "Education",
        "Certifications",
        "Priorities",
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

    percentage = min(max(step - 1, 0), 5) * 20

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
        "About You",
        "Experience",
        "Education",
        "Certifications",
        "Priorities",
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
        1: "Your declared location and languages provide personal context.",
        2: "Your confirmed answers preserve your own account of your work.",
        3: "Your education records preserve the qualifications you declare.",
        4: "Your certification records preserve what you earned and when.",
        5: "Your declaration records what matters when choosing opportunities.",
        6: "Your source information is saved. Profile construction is a separate next step.",
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
            <span>Your information is private.</span>
        </div>
    </div>
    """

    st.html(html)


from components.company_interview import render_company_interview
from services.company_interview import start_interview, resume_interview


def render_onboarding(
    *,
    candidate_id,
    candidate_name,
    onboarding_repository,
    profile_gateway,
    authenticated_user,
    active_user,
    voice_inputs=None,
    reflection_provider=None,
):
    # profile_gateway is intentionally unused until RAW -> V1 is connected.
    if active_user.candidate_id != candidate_id or not AccessPolicy.can_access_candidate(authenticated_user, candidate_id):
        st.error("Access denied.")
        return
    scope = bind_scope(st.session_state, authenticated_user.id, active_user.id, candidate_id)
    prefix = "_voice_onboarding_v4_" + scope + "_"
    step_key = f"onboarding_step_{candidate_id}"
    draft_key = "_voice_company_draft_" + scope
    recovered = resume_interview(scope, candidate_id, onboarding_repository)
    draft = st.session_state.get(draft_key)
    if recovered is not None:
        if draft is None or draft.get("id") != recovered["id"]:
            draft = recovered
            st.session_state[draft_key] = draft
    elif draft is not None:
        st.session_state.pop(draft_key, None)
        draft = None
    if draft is not None and (draft.get("candidate_id") != candidate_id or draft.get("scope") != scope):
        st.error("Access denied.")
        return

    existing = (onboarding_repository.get_onboarding(candidate_id) if draft is None else None) or CandidateOnboarding(candidate_id)
    experiences = onboarding_repository.list_work_experiences(candidate_id) if draft is None else []
    about_ready = bool(existing.country.strip() and existing.city.strip() and existing.spoken_languages)
    current = st.session_state.get(step_key)
    if draft is not None:
        step = 2
    elif not about_ready:
        step = 1
    elif not experiences:
        step = 1 if current == 1 else 2
    else:
        step = current if type(current) is int and 1 <= current <= 6 else 3
    st.session_state[step_key] = step

    def go(destination):
        st.session_state[step_key] = destination
        st.rerun()

    def back():
        if st.button("Back", key=prefix + "back"):
            go(step - 1)

    _render_workpilot_stepper(step)
    main_col, side_col = st.columns([3.25, 1.15], gap="large")
    with side_col:
        _render_workpilot_side_panel(step)
    with main_col:
        if step == 1:
            st.subheader("About You")
            countries = list(COUNTRY_NAMES)
            if existing.country and existing.country not in countries:
                countries.append(existing.country)
            country = st.selectbox("Country", countries,
                index=countries.index(existing.country) if existing.country else None,
                key=prefix + "country")
            city = st.text_input("City", value=existing.city, key=prefix + "city") if country else ""
            language_options = list(dict.fromkeys(LANGUAGE_OPTIONS + existing.spoken_languages))
            languages = st.multiselect("Languages", language_options, default=existing.spoken_languages,
                accept_new_options=True, key=prefix + "languages")
            if st.button("Continue", type="primary", key=prefix + "continue"):
                if not country or not city.strip() or not languages:
                    st.warning("Add country, city and at least one language before continuing.")
                else:
                    onboarding_repository.save_onboarding(replace(existing, country=country,
                        city=city.strip(), spoken_languages=languages))
                    go(2)
        elif step == 2:
            st.subheader("Professional Experience")
            if draft is not None:
                inputs = voice_inputs or VoiceTextInputs(scope, events=OnboardingEventRepository(
                    authenticated_user.id, active_user.id, candidate_id))
                render_company_interview(draft, scope, onboarding_repository, inputs,
                    reflection_provider=reflection_provider)
                return
            for experience in experiences:
                st.write(experience.company)
                st.write(experience.role or "Role not provided")
                st.caption(_format_month_year(experience.start_date) + " - " +
                           (_format_month_year(experience.end_date) if experience.end_date else "Present"))
                if st.button("Remove", key=prefix + "remove_experience_" + experience.id):
                    onboarding_repository.delete_work_experience(experience.id, candidate_id)
                    st.rerun()
            with st.form(prefix + "company_metadata"):
                company = st.text_input("Company", key=prefix + "company")
                role = st.text_input("Role", key=prefix + "role")
                months = list(range(1, 13))
                years = list(range(date.today().year, 1899, -1))
                start_month = st.selectbox("Start month", months, index=None,
                    format_func=lambda m: calendar.month_name[m], key=prefix + "start_month")
                start_year = st.selectbox("Start year", years, index=None, key=prefix + "start_year")
                current_role = st.checkbox("I currently work here", key=prefix + "current_role")
                end_month = st.selectbox("End month", months, index=None,
                    format_func=lambda m: calendar.month_name[m], key=prefix + "end_month")
                end_year = st.selectbox("End year", years, index=None, key=prefix + "end_year")
                begin = st.form_submit_button("Start company interview", type="primary")
            if begin:
                if (not company.strip() or not role.strip() or not start_month or not start_year
                        or (not current_role and (not end_month or not end_year))):
                    st.warning("Add company, role and dates before continuing.")
                else:
                    try:
                        st.session_state[draft_key] = start_interview(
                            scope, candidate_id, company.strip(), f"{start_year:04d}-{start_month:02d}",
                            None if current_role else f"{end_year:04d}-{end_month:02d}",
                            role=role.strip(), version=V4_VERSION, repository=onboarding_repository)
                    except ValueError:
                        st.warning("Check company, role and dates.")
                    else:
                        st.rerun()
            back()
            if st.button("Continue", type="primary", key=prefix + "continue"):
                if not experiences:
                    st.warning("Add at least one completed experience before continuing.")
                else:
                    go(3)
        elif step == 3:
            st.subheader("Education")
            for record in onboarding_repository.list_education(candidate_id):
                st.write(f"{record.institution} - {record.qualification} - {record.field}")
                if st.button("Remove", key=prefix + "remove_education_" + record.id):
                    onboarding_repository.delete_education(record.id, candidate_id)
                    st.rerun()
            # Outside the form so selecting Other reveals its input immediately.
            qualification_choice = st.selectbox("Qualification", QUALIFICATION_OPTIONS,
                index=None, key=prefix + "qualification_choice")
            with st.form(prefix + "education", clear_on_submit=True):
                institution = st.text_input("Institution", key=prefix + "institution")
                qualification = (st.text_input("Other qualification", key=prefix + "qualification_other")
                    if qualification_choice == "Other" else qualification_choice or "")
                field = st.text_input("Field", key=prefix + "field")
                add = st.form_submit_button("Add education")
            if add:
                try:
                    if not qualification.strip():
                        raise ValueError("Qualification is required.")
                    onboarding_repository.add_education(candidate_id=candidate_id, institution=institution.strip(),
                        qualification=qualification.strip(), field=field.strip())
                except ValueError:
                    st.warning("Add institution, qualification and field.")
                else:
                    st.rerun()
            back()
            if st.button("Continue", type="primary", key=prefix + "continue"):
                go(4)
        elif step == 4:
            st.subheader("Certifications")
            for record in onboarding_repository.list_certifications(candidate_id):
                st.write(f"{record.name} - {record.issuer} - {record.year_obtained}")
                if st.button("Remove", key=prefix + "remove_certification_" + record.id):
                    onboarding_repository.delete_certification(record.id, candidate_id)
                    st.rerun()
            with st.form(prefix + "certification", clear_on_submit=True):
                name = st.text_input("Certification name", key=prefix + "cert_name")
                issuer = st.text_input("Issuer", key=prefix + "issuer")
                year = st.number_input("Year obtained", min_value=1, max_value=9999, value=date.today().year, step=1,
                    key=prefix + "year_obtained")
                add = st.form_submit_button("Add certification")
            if add:
                try:
                    onboarding_repository.add_certification(candidate_id=candidate_id, name=name.strip(),
                        issuer=issuer.strip(), year_obtained=year)
                except ValueError:
                    st.warning("Add certification name, issuer and an integer year.")
                else:
                    st.rerun()
            back()
            if st.button("Continue", type="primary", key=prefix + "continue"):
                go(5)
        elif step == 5:
            st.subheader("Priorities")
            st.caption("What matters when choosing opportunities, such as salary, remote work, location or weekends.")
            declaration = st.text_area("What matters to you when choosing your next opportunity?",
                value=existing.priority_declaration, key=prefix + "priority_declaration")
            back()
            if st.button("Continue", type="primary", key=prefix + "continue"):
                onboarding_repository.save_onboarding(replace(existing, priority_declaration=declaration.strip()))
                go(6)
            if st.button("I'll add these later", key=prefix + "skip_priorities"):
                go(6)
        elif step == 6:
            st.success("Your information is saved and ready for profile construction.")
            back()
