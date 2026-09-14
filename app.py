import streamlit as st

from components.job_analysis_view import render_job_analysis

from services.candidate_repository import CandidateRepository
from services.session_auth import (
    render_logout_button,
    require_authenticated_user,
)
from services.user_context_runtime import get_active_user_context
from services.application_outcome_repository import ApplicationOutcomeRepository
from services.application_outcome_service import ApplicationOutcomeService
from services.application_outcome_ui import (
    dispatch_application_outcome_action,
    load_application_outcome_view,
    outcome_result_message,
)
from models.interview_context import InterviewDetails
from services.interview_context_service import InterviewContextService
from services.interview_details_repository import InterviewDetailsRepository
from services.interview_preparation_service import InterviewPreparationService
from services.interview_preparation_ui import (
    handle_interview_details_save,
    load_interview_preparation_view,
)
from services.database import (
    count_candidate_jobs_by_status,
    initialize_database,
    list_candidate_jobs,
    update_candidate_job_notes,
)



DASHBOARD_CSS = """
<style>
    .wp-dashboard-eyebrow {
        color: #075665;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        margin-bottom: 0.55rem;
    }

    .wp-dashboard-title {
        color: #18363D;
        font-size: 2.45rem;
        line-height: 1.08;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin-bottom: 0.45rem;
    }

    .wp-dashboard-copy {
        color: #65777C;
        font-size: 1rem;
        line-height: 1.55;
        margin-bottom: 1.7rem;
        max-width: 720px;
    }

    .wp-dashboard-section {
        color: #18363D;
        font-size: 1.15rem;
        font-weight: 750;
        margin-top: 1.7rem;
        margin-bottom: 0.25rem;
    }

    .wp-dashboard-section-copy {
        color: #738388;
        font-size: 0.88rem;
        margin-bottom: 0.9rem;
    }

    .wp-stat-card {
        background: #FFFFFF;
        border: 1px solid #DFE7E7;
        border-radius: 14px;
        padding: 1.05rem 1.15rem;
        min-height: 105px;
        box-shadow:
            0 2px 10px rgba(7, 62, 73, 0.025);
    }

    .wp-stat-label {
        color: #6C7D81;
        font-size: 0.78rem;
        font-weight: 650;
        margin-bottom: 0.35rem;
    }

    .wp-stat-value {
        color: #18363D;
        font-size: 2rem;
        line-height: 1;
        font-weight: 750;
    }

    [data-testid="stTabs"] {
        margin-top: 0.35rem;
    }

    [data-testid="stExpander"] {
        border: 1px solid #DFE7E7 !important;
        border-radius: 12px !important;
        overflow: hidden;
        background: #FFFFFF !important;
    }

    [data-testid="stExpander"] details summary {
        background: #FFFFFF !important;
        color: #18363D !important;
    }

    [data-testid="stExpander"] details summary * {
        color: #18363D !important;
    }
</style>
"""


def render_dashboard_stat(
    label: str,
    value: int,
) -> None:
    st.html(
        f"""
        <div class="wp-stat-card">
            <div class="wp-stat-label">
                {label}
            </div>
            <div class="wp-stat-value">
                {value}
            </div>
        </div>
        """
    )


STATUS_LABELS = {
    "system_rejected": "System rejected",
    "in_review": "In review",
    "user_rejected": "Not applied",
    "applied": "Applied",
    "rejected_before_interview": "Rejected before interview",
    "in_process": "In process",
    "rejected_after_interview": "Rejected after interview",
    "offer": "Offer",
}


def render_list(
    title: str,
    items: list[str],
) -> None:
    st.subheader(title)

    if not items:
        st.caption("No information available.")
        return

    for item in items:
        st.write(f"- {item}")


def render_text_section(
    title: str,
    text: str,
    empty_message: str,
) -> None:
    st.subheader(title)

    if text:
        st.write(text)
    else:
        st.caption(empty_message)


def save_notes(
    candidate_id: str,
    job_id: str,
    notes: str,
) -> None:
    update_candidate_job_notes(
        candidate_id=candidate_id,
        job_id=job_id,
        notes=notes,
    )

    st.toast("Notes saved.")


def render_application_outcome(
    candidate_id: str,
    job_id: str,
    status: str,
) -> None:
    repository = ApplicationOutcomeRepository()
    service = ApplicationOutcomeService(repository=repository)
    view = load_application_outcome_view(
        candidate_id=candidate_id,
        job_id=job_id,
        lifecycle_status=status,
        repository=repository,
    )
    if view is None:
        return

    st.divider()
    st.subheader("Application status")
    st.markdown(f"**{view.status_label}**")

    if not view.actions:
        st.caption("This application has a final outcome.")
        return

    action_by_label = {item.label: item.value for item in view.actions}
    selected_label = st.selectbox(
        "Next step",
        options=list(action_by_label),
        key=f"outcome_action_{candidate_id}_{job_id}",
    )
    selected_action = action_by_label[selected_label]
    existing = view.outcome

    rejection_reason = ""
    recruiter_feedback = ""
    if selected_action == "rejected":
        rejection_reason = st.text_area(
            "Rejection reason",
            value=existing.rejection_reason if existing else "",
            key=f"outcome_rejection_{candidate_id}_{job_id}",
            placeholder="Optional",
        )
        recruiter_feedback = st.text_area(
            "Recruiter / company feedback",
            value=existing.recruiter_feedback if existing else "",
            key=f"outcome_feedback_{candidate_id}_{job_id}",
            placeholder="Optional",
        )

    candidate_notes = st.text_area(
        "Your notes",
        value=existing.candidate_notes if existing else "",
        placeholder="Optional",
        key=f"outcome_notes_{candidate_id}_{job_id}",
    )

    offer_salary = ""
    offer_currency = ""
    if selected_action == "offer":
        offer_columns = st.columns(2)
        with offer_columns[0]:
            offer_salary = st.text_input(
                "Offer salary",
                value=existing.offer_salary if existing else "",
                key=f"outcome_salary_{candidate_id}_{job_id}",
                placeholder="Optional",
            )
        with offer_columns[1]:
            offer_currency = st.text_input(
                "Currency",
                value=existing.offer_currency if existing else "",
                placeholder="Optional",
                key=f"outcome_currency_{candidate_id}_{job_id}",
            )

    confirmed = st.button(
        "Confirm update",
        key=f"confirm_outcome_{candidate_id}_{job_id}",
        type="primary",
        use_container_width=True,
    )
    result = dispatch_application_outcome_action(
        confirmed=confirmed,
        action=selected_action,
        candidate_id=candidate_id,
        job_id=job_id,
        lifecycle_status=status,
        service=service,
        rejection_reason=rejection_reason,
        recruiter_feedback=recruiter_feedback,
        candidate_notes=candidate_notes,
        offer_salary=offer_salary,
        offer_currency=offer_currency,
    )
    if result is not None:
        message = outcome_result_message(result)
        if result.succeeded:
            st.toast(message)
            st.rerun()
        else:
            st.error(message)


def render_interview_preparation(
    candidate_id: str,
    job_id: str,
    status: str,
) -> None:
    details_repository = InterviewDetailsRepository()
    context_service = InterviewContextService(
        details_repository=details_repository,
    )
    preparation_service = InterviewPreparationService(
        context_service=context_service,
    )
    result = load_interview_preparation_view(
        candidate_id=candidate_id,
        job_id=job_id,
        lifecycle_status=status,
        context_service=context_service,
        preparation_service=preparation_service,
        details_repository=details_repository,
    )
    if result.error_message:
        st.error(result.error_message)
        return
    if not result.visible or result.view is None or result.details is None:
        return

    view = result.view
    details = result.details
    st.divider()
    st.subheader(view.title)
    identity = " · ".join(value for value in (view.role, view.company) if value)
    if identity:
        st.markdown(f"**{identity}**")
    metadata = [
        value
        for value in (
            view.stage,
            view.interview_type,
            view.interview_format,
            view.interviewer,
            view.duration,
            view.scheduled_at,
        )
        if value
    ]
    if metadata:
        st.caption(" · ".join(metadata))
    if view.summary_guidance:
        st.info(view.summary_guidance)

    if view.interview_instructions:
        st.markdown("**Interview instructions**")
        for instruction in view.interview_instructions:
            st.write(instruction)

    for area in view.preparation_areas:
        st.markdown(f"#### {area.topic}")
        st.caption(area.priority_label)
        if area.source_label:
            st.markdown(f"**{area.source_label}**")
        if area.what_to_demonstrate:
            st.markdown("**What to demonstrate**")
            st.write(area.what_to_demonstrate)
        if area.example_direction:
            st.markdown("**Look for a real example where**")
            st.write(area.example_direction)
        if area.emphasis:
            st.markdown("**Emphasize**")
            st.write(area.emphasis)
        if area.caution:
            st.markdown("**Be careful**")
            st.warning(area.caution)

    if view.rehearsal_prompts:
        st.markdown("**Think through**")
        for prompt in view.rehearsal_prompts:
            st.write(f"- {prompt}")
    if view.questions_to_ask_the_company:
        st.markdown("**Questions to ask the company**")
        for question in view.questions_to_ask_the_company:
            st.write(f"- {question}")

    edit_details = st.toggle(
        "Edit interview details",
        key=f"edit_interview_details_{candidate_id}_{job_id}",
    )
    if edit_details:
        with st.form(f"interview_details_{candidate_id}_{job_id}"):
            interview_type = st.text_input(
                "Interview type",
                value=details.interview_type,
            )
            interview_format = st.text_input(
                "Format",
                value=details.interview_format,
            )
            interviewer = st.text_input(
                "Interviewer",
                value=details.interviewer,
            )
            duration_minutes = st.number_input(
                "Duration in minutes",
                min_value=0,
                step=5,
                value=details.duration_minutes or 0,
            )
            scheduled_at = st.text_input(
                "Scheduled time",
                value=details.scheduled_at,
            )
            instructions = st.text_area(
                "Instructions from the recruiter",
                value=details.instructions,
            )
            explicit_topics = st.text_area(
                "Topics explicitly mentioned",
                value="\n".join(details.explicit_topics),
                placeholder="One topic per line",
            )
            save_requested = st.form_submit_button(
                "Save interview details",
                type="primary",
            )

        if save_requested:
            updated = InterviewDetails(
                candidate_id=candidate_id,
                job_id=job_id,
                interview_type=interview_type,
                interview_format=interview_format,
                interviewer=interviewer,
                duration_minutes=(int(duration_minutes) or None),
                scheduled_at=scheduled_at,
                instructions=instructions,
                explicit_topics=[
                    value.strip()
                    for value in explicit_topics.splitlines()
                    if value.strip()
                ],
            )
            save_result = handle_interview_details_save(
                st.session_state,
                candidate_id=candidate_id,
                job_id=job_id,
                lifecycle_status=status,
                save_requested=True,
                details=updated,
                details_repository=details_repository,
                context_service=context_service,
                preparation_service=preparation_service,
            )
            if save_result.saved:
                st.toast("Interview details saved.")
                st.rerun()
            else:
                st.error(save_result.error_message)


def render_job(
    candidate_id: str,
    item: dict,
) -> None:
    analysis = item.get(
        "analysis",
        {},
    )

    job_id = str(item["id"])
    title = item.get(
        "title",
        "Untitled role",
    )
    company = item.get(
        "company",
        "Unknown company",
    )
    location = item.get(
        "location",
        "Location unavailable",
    )
    url = item.get("url")
    status = item.get(
        "status",
        "in_review",
    )
    notes = item.get(
        "notes",
        "",
    )

    current_fit = item.get(
        "current_fit",
        "-",
    )
    growth_value = item.get(
        "growth_value",
        "-",
    )
    recommendation = item.get(
        "recommendation",
        "unknown",
    )

    requirements_met = analysis.get(
        "requirements_met",
        [],
    )

    development_gaps = analysis.get(
        "development_gaps",
        [],
    )

    structural_gaps = analysis.get(
        "structural_gaps",
        [],
    )

    all_gaps = [
        *development_gaps,
        *structural_gaps,
    ]

    positive_points = analysis.get(
        "positive_points",
        [],
    )

    personal_tradeoffs = analysis.get(
        "personal_negatives",
        [],
    )

    reason = analysis.get(
        "reason",
        "",
    )

    final_recommendation = analysis.get(
        "final_reason",
        "",
    )

    simple_summary = analysis.get(
        "simple_summary",
        "",
    )

    simple_recommendation = analysis.get(
        "simple_recommendation",
        "",
    )

    label = f"{title} — {company}"

    with st.expander(
        label,
        expanded=False,
    ):

        status_label = STATUS_LABELS.get(
            status,
            status,
        )

        render_job_analysis(
            item,
            status_label=status_label,
        )

        render_interview_preparation(
            candidate_id=candidate_id,
            job_id=job_id,
            status=status,
        )

        st.divider()

        render_application_outcome(
            candidate_id=candidate_id,
            job_id=job_id,
            status=status,
        )

        st.subheader("Notes")

        notes_value = st.text_area(
            "Personal notes",
            value=notes,
            key=f"notes_{candidate_id}_{job_id}",
            label_visibility="collapsed",
            placeholder=(
                "Add salary information, interview notes, "
                "recruiter feedback, or reasons for your decision."
            ),
        )

        if st.button(
            "Save notes",
            key=f"save_notes_{job_id}",
        ):
            save_notes(
                job_id=job_id,
                notes=notes_value,
                candidate_id=candidate_id,
            )

        if url:
            st.link_button(
                "Open job",
                url,
            )


def render_job_section(
    candidate_id: str,
    status: str,
) -> None:
    jobs = list_candidate_jobs(
        candidate_id=candidate_id,
        status=status,
    )

    if not jobs:
        st.info(
            f"No jobs currently marked as "
            f"{STATUS_LABELS[status]}."
        )
        return

    for item in jobs:
        render_job(
            candidate_id,
            item,
        )


def main() -> None:
    st.set_page_config(
        page_title="WorkPilot",
        page_icon="ðŸŽ¯",
        layout="wide",
    )

    initialize_database()

    authenticated_user = (
        require_authenticated_user()
    )

    user_context = (
        get_active_user_context(
            authenticated_user=(
                authenticated_user
            )
        )
    )

    active_user = (
        user_context.active_user
    )

    render_logout_button()

    candidate_repository = CandidateRepository()

    st.markdown(
        DASHBOARD_CSS,
        unsafe_allow_html=True,
    )

    st.html(
        """
        <div class="wp-dashboard-eyebrow">
            YOUR CAREER
        </div>
        <div class="wp-dashboard-title">
            Career Dashboard
        </div>
        <div class="wp-dashboard-copy">
            Track your applications, follow your progress
            and keep what happens next in one place.
        </div>
        """
    )

    if not active_user.candidate_id:
        st.warning(
            "This account does not have a professional profile yet."
        )
        return

    selected_candidate_id = active_user.candidate_id

    candidate = candidate_repository.get(
        selected_candidate_id
    )

    if candidate is None:
        st.warning(
            "The professional profile could not be found."
        )
        return

    counts = count_candidate_jobs_by_status(
        selected_candidate_id
    )

    rejected_total = (
        counts["rejected_before_interview"]
        + counts["rejected_after_interview"]
    )

    metric_columns = st.columns(
        4,
        gap="medium",
    )

    with metric_columns[0]:
        render_dashboard_stat(
            "Applied",
            counts["applied"],
        )

    with metric_columns[1]:
        render_dashboard_stat(
            "In process",
            counts["in_process"],
        )

    with metric_columns[2]:
        render_dashboard_stat(
            "Rejected",
            rejected_total,
        )

    with metric_columns[3]:
        render_dashboard_stat(
            "Offers",
            counts["offer"],
        )

    st.html(
        """
        <div class="wp-dashboard-section">
            Applications
        </div>
        <div class="wp-dashboard-section-copy">
            Follow each application from submission
            through interview, rejection or offer.
        </div>
        """
    )

    tabs = st.tabs(
        [
            f"Applied ({counts['applied']})",
            f"In process ({counts['in_process']})",
            f"Rejected ({rejected_total})",
            f"Offers ({counts['offer']})",
        ]
    )

    with tabs[0]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="applied",
        )

    with tabs[1]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="in_process",
        )

    with tabs[2]:
        if counts["rejected_before_interview"]:
            st.subheader(
                "Rejected before interview"
            )

            render_job_section(
                candidate_id=selected_candidate_id,
                status="rejected_before_interview",
            )

        if (
            counts["rejected_before_interview"]
            and counts["rejected_after_interview"]
        ):
            st.divider()

        if counts["rejected_after_interview"]:
            st.subheader(
                "Rejected after interview"
            )

            render_job_section(
                candidate_id=selected_candidate_id,
                status="rejected_after_interview",
            )

        if not rejected_total:
            st.info(
                "No rejected applications."
            )

    with tabs[3]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="offer",
        )


if __name__ == "__main__":
    main()
