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
from services.product_mode_policy import product_mode_policy
from services.external_application import external_application_url
from services.system_state_presenter import application_age_state
from datetime import datetime, timezone
from services.database import (
    initialize_database,
    list_candidate_jobs,
    update_candidate_job_notes,
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
    *,
    read_only: bool = False,
    compact: bool = False,
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

    if compact:
        st.caption(f"Current status: {view.status_label}")
    else:
        st.divider()
        st.subheader("Application status")
        st.markdown(f"**{view.status_label}**")

    if read_only:
        st.caption(
            "Read-only access. Application history is preserved."
        )
        return

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

    friendly_labels = {
        "Interview": "I got an interview",
        "Final interview": "I have another interview",
        "Offer": "I got an offer",
        "Accepted": "Accept offer",
        "Declined": "Decline offer",
        "Rejected": "I was rejected",
        "Withdrawn": "I withdrew",
        "No response": "No response",
    }

    action_by_label = {
        (
            friendly_labels.get(item.label, item.label)
            if compact
            else item.label
        ): item.value
        for item in view.actions
    }

    action_options = list(
        action_by_label
    )

    if compact:
        action_options = [
            "Select an update...",
            *action_options,
        ]

    selected_label = st.selectbox(
        "What changed?" if compact else "Next step",
        options=action_options,
        index=0,
        key=f"outcome_action_{candidate_id}_{job_id}",
    )

    selected_action = action_by_label.get(
        selected_label
    )

    existing = view.outcome

    rejection_reason = ""
    recruiter_feedback = ""
    candidate_notes = ""
    offer_salary = ""
    offer_currency = ""

    if selected_action:
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
            "Save update" if compact else "Confirm update",
            key=f"confirm_outcome_{candidate_id}_{job_id}",
            type="primary",
            use_container_width=True,
        )
    else:
        confirmed = False

        if compact:
            st.caption(
                "Choose an update before saving."
            )

    result = None

    if selected_action:
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
    *,
    read_only: bool = False,
    compact: bool = False,
) -> None:
    from services.interview_preparation_ui import (
        render_interview_preparation_overview,
        render_interview_rounds,
    )

    if compact:
        render_interview_preparation_overview(
            st,
            candidate_id=candidate_id,
            job_id=job_id,
            lifecycle_status=status,
            read_only=read_only,
        )

        st.divider()
        st.markdown("#### Interview rounds")

    render_interview_rounds(
        st,
        candidate_id=candidate_id,
        job_id=job_id,
        read_only=read_only,
        compact=compact,
    )


def render_job(
    candidate_id: str,
    item: dict,
    *,
    read_only: bool = False,
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
        if (
            item.get("application_stage") == "ready_to_apply"
            and not read_only
        ):
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
            read_only=read_only,
        )

        st.divider()

        render_application_outcome(
            candidate_id=candidate_id,
            job_id=job_id,
            status=status,
            read_only=read_only,
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
            disabled=read_only,
        )

        if (
            not read_only
            and st.button(
                "Save notes",
                key=f"save_notes_{job_id}",
            )
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


def _application_filter_group(item) -> str:
    """Presentation grouping only. Domain state remains authoritative."""
    group = str(item.get("application_group") or "")
    stage = str(item.get("application_stage") or "")

    if (
        group == "no_response"
        or stage in {
            "accepted",
            "declined",
            "rejected",
            "withdrawn",
            "no_response",
        }
    ):
        return "closed"

    if group in {"applied", "interview", "offer", "closed"}:
        return group

    return ""


def _application_status_label(item) -> str:
    stage = str(item.get("application_stage") or "")

    labels = {
        "applied": "Applied",
        "interview": "Interview",
        "final_interview": "Interview",
        "offer": "Offer",
        "accepted": "Accepted",
        "declined": "Declined",
        "rejected": "Rejected",
        "withdrawn": "Withdrawn",
        "no_response": "No response",
    }

    return labels.get(
        stage,
        stage.replace("_", " ").title() if stage else "Application",
    )


def _application_attention_message(item) -> str:
    """Surface only states with a concrete action available now."""
    group = _application_filter_group(item)

    if group == "offer":
        return "An offer is waiting for your decision."

    if group != "applied":
        return ""

    applied_at = str(item.get("applied_at") or "")
    if not applied_at:
        return ""

    from datetime import datetime, timezone
    from services.system_state_presenter import application_age_state

    state = application_age_state(
        applied_at=applied_at,
        now=datetime.now(timezone.utc).isoformat(),
    )

    if state is None or not state.action_prompt:
        return ""

    return f"{state.action_prompt} {state.title}"


def _render_application_summary(item) -> None:
    """Compact presentation card. No domain decisions are made here."""
    from html import escape

    title = escape(str(item.get("title") or "Untitled role"))
    company = escape(str(item.get("company") or "Company not available"))
    location = escape(str(item.get("location") or ""))
    status = escape(_application_status_label(item))

    round_count = item.get("round_count") or 0

    meta = [company]

    if location:
        meta.append(location)

    try:
        rounds = int(round_count)
    except (TypeError, ValueError):
        rounds = 0

    if rounds:
        meta.append(
            f"{rounds} interview round"
            + ("" if rounds == 1 else "s")
        )

    meta_text = " ? ".join(escape(str(value)) for value in meta)

    group = _application_filter_group(item)
    tone = (
        "offer"
        if group == "offer"
        else "interview"
        if group == "interview"
        else "closed"
        if group == "closed"
        else "applied"
    )

    st.html(
        f"""
        <section class="wp-application-card">
            <div class="wp-application-card-main">
                <h3>{title}</h3>
                <p>{meta_text}</p>
            </div>
            <span class="wp-application-status wp-application-status-{tone}">
                {status}
            </span>
        </section>
        """
    )



def _render_application_details(
    candidate_id: str,
    item: dict,
    *,
    read_only: bool = False,
) -> None:
    """Stage-focused Applications UI. Existing services remain authoritative."""
    from datetime import datetime, timezone
    from html import escape

    from services.system_state_presenter import application_age_state

    job_id = str(item["id"])
    status = str(item.get("status") or "applied")
    group = _application_filter_group(item)
    stage_label = _application_status_label(item)

    notes = str(item.get("notes") or "")
    url = item.get("url")

    age = application_age_state(
        applied_at=item.get("applied_at"),
        now=datetime.now(timezone.utc).isoformat(),
    )

    if group == "applied":
        st.markdown("#### Waiting for an update")

        if age is not None:
            if age.action_prompt:
                st.caption(
                    f"{age.title} - {age.action_prompt}"
                )
            else:
                st.caption(age.title)

        st.write(
            "When something changes, update this application here. "
            "WorkPilot will keep the application history and move the "
            "next step forward."
        )

        if not read_only:
            with st.expander(
                "Update application",
                expanded=False,
            ):
                render_application_outcome(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    status=status,
                    read_only=False,
                    compact=True,
                )

        else:
            render_application_outcome(
                candidate_id=candidate_id,
                job_id=job_id,
                status=status,
                read_only=True,
                compact=True,
            )

    elif group == "interview":
        st.markdown("#### Interview")

        st.write(
            "Prepare from the evidence WorkPilot already has, then keep "
            "each interview round separate so feedback and next steps "
            "stay connected to the right stage."
        )

        render_interview_preparation(
            candidate_id=candidate_id,
            job_id=job_id,
            status=status,
            read_only=read_only,
            compact=True,
        )

        if not read_only:
            with st.expander(
                "Update application status",
                expanded=False,
            ):
                render_application_outcome(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    status=status,
                    read_only=False,
                    compact=True,
                )

    elif group == "offer":
        st.markdown("#### Offer")

        outcome = ApplicationOutcomeRepository().get(
            candidate_id,
            job_id,
        )

        if outcome is not None:
            offer_parts = []

            if outcome.offer_salary:
                offer_parts.append(str(outcome.offer_salary))

            if outcome.offer_currency:
                offer_parts.append(str(outcome.offer_currency))

            if offer_parts:
                st.html(
                    f"""
                    <div class="wp-offer-summary">
                        <span>Recorded offer</span>
                        <strong>{escape(" ".join(offer_parts))}</strong>
                    </div>
                    """
                )

        st.write(
            "Review the offer and record your decision when you are ready."
        )

        render_application_outcome(
            candidate_id=candidate_id,
            job_id=job_id,
            status=status,
            read_only=read_only,
            compact=True,
        )

    elif group == "closed":
        st.markdown("#### Final outcome")

        render_application_outcome(
            candidate_id=candidate_id,
            job_id=job_id,
            status=status,
            read_only=read_only,
            compact=True,
        )

    st.markdown(
        '<div class="wp-application-detail-divider"></div>',
        unsafe_allow_html=True,
    )

    with st.expander(
        "Notes",
        expanded=False,
    ):
        notes_value = st.text_area(
            "Personal notes",
            value=notes,
            key=f"application_notes_{candidate_id}_{job_id}",
            label_visibility="collapsed",
            placeholder=(
                "Add recruiter feedback, decision context, "
                "or anything you want to remember."
            ),
            disabled=read_only,
        )

        if (
            not read_only
            and st.button(
                "Save notes",
                key=f"application_save_notes_{candidate_id}_{job_id}",
            )
        ):
            save_notes(
                job_id=job_id,
                notes=notes_value,
                candidate_id=candidate_id,
            )

    try:
        safe_url = (
            external_application_url(url)
            if url
            else ""
        )
    except ValueError:
        safe_url = ""

    if safe_url:
        st.link_button(
            "Open job posting",
            safe_url,
        )


def applications_main() -> None:
    st.set_page_config(
        page_title="Applications | WorkPilot",
        page_icon=":material/assignment:",
        layout="wide",
    )

    if get_authenticated_user() is None:
        render_public_landing()
        st.stop()

    initialize_database()

    authenticated_user = require_authenticated_user()

    user_context = get_active_user_context(
        authenticated_user=authenticated_user
    )

    active_user = user_context.active_user

    render_logout_button()

    candidate_repository = CandidateRepository()

    from components.workpilot_ui import (
        apply_theme,
        empty_state,
        page_header,
    )

    apply_theme()

    page_header(
        "Applications",
        "Track what is moving, what needs your attention, and what comes next.",
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

    product_state = CandidateProductStateRepository().get(
        selected_candidate_id
    )

    product_policy = product_mode_policy(product_state)
    read_only = not product_policy.can_mutate

    if read_only:
        st.info(
            "WorkPilot is in read-only mode. "
            "Your application and interview history remains available, "
            "but it cannot be changed."
        )

    elif product_policy.mode.value == "career":
        st.caption(
            "Career mode is active. "
            "New opportunity searches are paused."
        )

    raw_applications = (
        ApplicationOutcomeRepository()
        .list_applications(selected_candidate_id)
    )

    # Ready-to-apply belongs to Jobs. Applications begins only once
    # the candidate has explicitly confirmed an application.
    applications = [
        item
        for item in raw_applications
        if _application_filter_group(item)
    ]

    if not applications:
        empty_state(
            "No applications yet",
            "Applications appear here after you confirm that you applied.",
        )
        return

    attention = [
        (item, _application_attention_message(item))
        for item in applications
    ]
    attention = [
        (item, message)
        for item, message in attention
        if message
    ]

    if attention:
        st.markdown("### Needs your attention")
        st.caption(
            "Only applications with a concrete next action appear here."
        )

        for item, message in attention[:3]:
            title = str(item.get("title") or "Untitled role")
            company = str(
                item.get("company") or "Company not available"
            )

            st.html(
                f"""
                <section class="wp-application-attention">
                    <div>
                        <strong>{title}</strong>
                        <span>{company}</span>
                    </div>
                    <p>{message}</p>
                </section>
                """
            )

        st.markdown(
            '<div class="wp-section-space"></div>',
            unsafe_allow_html=True,
        )

    filter_order = (
        "All",
        "Applied",
        "Interview",
        "Offer",
        "Closed",
    )

    group_by_filter = {
        "Applied": "applied",
        "Interview": "interview",
        "Offer": "offer",
        "Closed": "closed",
    }

    counts = {
        "All": len(applications),
        **{
            label: sum(
                1
                for item in applications
                if _application_filter_group(item) == group
            )
            for label, group in group_by_filter.items()
        },
    }

    st.markdown("### Your applications")

    selected_filter = st.radio(
        "Application status",
        options=filter_order,
        horizontal=True,
        label_visibility="collapsed",
        format_func=lambda label: f"{label} ({counts[label]})",
        key="applications_filter",
    )

    if selected_filter == "All":
        visible = applications
    else:
        selected_group = group_by_filter[selected_filter]

        visible = [
            item
            for item in applications
            if _application_filter_group(item) == selected_group
        ]

    if not visible:
        empty_state(
            f"No {selected_filter.lower()} applications",
            "Nothing in your application history matches this filter.",
        )
        return

    for item in visible:
        _render_application_summary(item)

        # A server action, not a client-only expander that opens before content
        # has arrived. Never render an empty interactive details panel.
        details_key = f"application_details_{selected_candidate_id}_{item['id']}"
        if st.button("View application details", key=details_key):
            st.session_state[details_key + "_open"] = True
        if st.session_state.get(details_key + "_open", False):
            with st.spinner("Loading application details..."):
                _render_application_details(
                    selected_candidate_id, item, read_only=read_only,
                )



def main():
    if get_authenticated_user() is None:
        render_public_landing()
        st.stop()
    # Cookie recovery can finish while only public routes are registered.
    # Let the shell rebuild navigation before rendering private page links.
    if st.session_state.get("workpilot_public_navigation", False):
        return
    from components.dashboard import render_dashboard
    authenticated = require_authenticated_user()
    active = get_active_user_context(authenticated_user=authenticated).active_user
    render_dashboard(active)


if __name__ == "__main__":
    main()
