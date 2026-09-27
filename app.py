import streamlit as st
from components.public_landing import render_public_landing

from components.job_analysis_view import render_job_analysis

from services.candidate_repository import CandidateRepository
from services.session_auth import (
    get_authenticated_user,
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
from services.application_lifecycle_service import ApplicationLifecycleService
from services.application_lifecycle_ui import handle_mark_applied_action
from models.product_state import HiredNextAction
from services.candidate_product_state_repository import (
    CandidateProductStateRepository,
)
from services.candidate_product_state_service import (
    HiredTransitionService,
)
from services.external_application import external_application_url
from services.system_state_presenter import application_age_state
from datetime import datetime, timezone
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
        if view.state == "accepted":
            product_state_repository = CandidateProductStateRepository()

            st.success("You accepted this role.")
            st.write("What would you like WorkPilot to do next?")

            keep_searching, switch_career, end_subscription = st.columns(3)

            with keep_searching:
                if st.button(
                    "Keep searching",
                    key=f"hired_keep_searching_{candidate_id}_{job_id}",
                    use_container_width=True,
                ):
                    HiredTransitionService(
                        repository=product_state_repository,
                    ).choose(
                        candidate_id=candidate_id,
                        job_id=job_id,
                        action=HiredNextAction.KEEP_SEARCHING,
                    )
                    st.rerun()

            with switch_career:
                if st.button(
                    "Switch to Career",
                    key=f"hired_switch_career_{candidate_id}_{job_id}",
                    use_container_width=True,
                ):
                    HiredTransitionService(
                        repository=product_state_repository,
                    ).choose(
                        candidate_id=candidate_id,
                        job_id=job_id,
                        action=HiredNextAction.SWITCH_TO_CAREER,
                    )
                    st.rerun()

            with end_subscription:
                if st.button(
                    "End subscription",
                    key=f"hired_end_subscription_{candidate_id}_{job_id}",
                    use_container_width=True,
                ):
                    HiredTransitionService(
                        repository=product_state_repository,
                    ).choose(
                        candidate_id=candidate_id,
                        job_id=job_id,
                        action=HiredNextAction.END_SUBSCRIPTION,
                    )
                    st.rerun()

            product_state = product_state_repository.get(candidate_id)

            if product_state.subscription_end_requested:
                st.info(
                    "Your request to end the subscription has been recorded. "
                    "Your access has not been changed until billing confirms it."
                )
            elif product_state.mode.value == "career":
                st.info("WorkPilot is now in Career mode.")
            else:
                st.caption("WorkPilot remains in Search mode.")

        else:
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


def render_interview_preparation(candidate_id: str, job_id: str, status: str) -> None:
    from services.interview_preparation_ui import render_interview_rounds
    render_interview_rounds(st, candidate_id=candidate_id, job_id=job_id)


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

        status_label = item.get("application_stage", status).replace("_", " ").title()

        render_job_analysis(
            item,
            status_label=status_label,
        )

        age = application_age_state(applied_at=item.get("applied_at"), now=datetime.now(timezone.utc).isoformat())
        if age:
            st.caption(age.title)
        if item.get("application_stage") == "ready_to_apply":
            confirmed = st.button("Yes, I applied", key=f"confirm_applied:{candidate_id}:{job_id}")
            result = handle_mark_applied_action(action_requested=confirmed, candidate_id=candidate_id,
                job_id=job_id, lifecycle_service=ApplicationLifecycleService())
            if result is not None:
                if result.succeeded:
                    st.rerun()
                st.warning("This application changed. Refresh before continuing.")

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

        try:
            safe_url = external_application_url(url) if url else ""
        except ValueError:
            safe_url = ""
        if safe_url:
            st.link_button(
                "Open job",
                safe_url,
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

    if get_authenticated_user() is None:
        render_public_landing()
        st.stop()

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

    applications = ApplicationOutcomeRepository().list_applications(selected_candidate_id)
    groups = [
        ("ready_to_apply", "Ready to apply"), ("applied", "Applied"),
        ("interview", "Interview"), ("offer", "Offer"),
        ("closed", "Closed"), ("no_response", "No Response"),
    ]
    grouped = {key: [item for item in applications if item["application_group"] == key] for key, _ in groups}
    st.subheader("Applications")
    tabs = st.tabs([f"{label} ({len(grouped[key])})" for key, label in groups])
    for tab, (key, label) in zip(tabs, groups):
        with tab:
            if not grouped[key]:
                st.info(f"No applications: {label}.")
            for item in grouped[key]:
                render_job(selected_candidate_id, item)


if __name__ == "__main__":
    main()
