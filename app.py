import streamlit as st

from components.job_analysis_view import render_job_analysis

from services.candidate_repository import CandidateRepository
from services.session_auth import require_login, render_logout_button
from services.database import (
    count_candidate_jobs_by_status,
    get_candidate_application_outcome,
    initialize_database,
    list_candidate_jobs,
    save_candidate_application_outcome,
    update_candidate_job_notes,
    update_candidate_job_status,
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


def change_status(
    candidate_id: str,
    job_id: str,
    new_status: str,
) -> None:
    update_candidate_job_status(
        candidate_id=candidate_id,
        job_id=job_id,
        status=new_status,
    )

    st.rerun()


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


def render_status_buttons(
    candidate_id: str,
    job_id: str,
    current_status: str,
) -> None:
    st.subheader("Application status")

    if current_status == "system_rejected":
        if st.button(
            "Move to In review",
            key=f"in_review_{candidate_id}_{job_id}",
            use_container_width=True,
        ):
            change_status(
                candidate_id,
                job_id,
                "in_review",
            )

        return

    if current_status == "in_review":
        columns = st.columns(2)

        with columns[0]:
            if st.button(
                "Do not apply",
                key=f"user_rejected_{candidate_id}_{job_id}",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "user_rejected",
                )

        with columns[1]:
            if st.button(
                "Mark as Applied",
                key=f"applied_{candidate_id}_{job_id}",
                type="primary",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "applied",
                )

        return

    if current_status == "user_rejected":
        if st.button(
            "Move back to In review",
            key=f"restore_review_{candidate_id}_{job_id}",
            use_container_width=True,
        ):
            change_status(
                candidate_id,
                job_id,
                "in_review",
            )

        return

    if current_status == "applied":
        columns = st.columns(2)

        with columns[0]:
            if st.button(
                "Rejected before interview",
                key=f"rejected_before_{candidate_id}_{job_id}",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "rejected_before_interview",
                )

        with columns[1]:
            if st.button(
                "Moved to interview process",
                key=f"in_process_{candidate_id}_{job_id}",
                type="primary",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "in_process",
                )

        return

    if current_status == "in_process":
        columns = st.columns(2)

        with columns[0]:
            if st.button(
                "Rejected in process",
                key=f"rejected_after_{candidate_id}_{job_id}",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "rejected_after_interview",
                )

        with columns[1]:
            if st.button(
                "Mark as Offer",
                key=f"offer_{candidate_id}_{job_id}",
                type="primary",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "offer",
                )

        return

    if current_status in {
        "rejected_before_interview",
        "rejected_after_interview",
        "offer",
    }:
        if st.button(
            "Move back to In process",
            key=f"restore_process_{candidate_id}_{job_id}",
            use_container_width=True,
        ):
            change_status(
                candidate_id,
                job_id,
                "in_process",
            )


def render_application_outcome(
    candidate_id: str,
    job_id: str,
    status: str,
) -> None:
    if status not in {
        "in_process",
        "rejected_before_interview",
        "rejected_after_interview",
        "offer",
    }:
        return

    outcome = (
        get_candidate_application_outcome(
            candidate_id=candidate_id,
            job_id=job_id,
        )
        or {}
    )

    st.divider()
    st.subheader("Application Outcome")

    interview_stage = st.text_input(
        "Interview stage",
        value=outcome.get(
            "interview_stage",
            "",
        ),
        placeholder=(
            "Example: recruiter screen, "
            "technical interview, final round"
        ),
        key=f"outcome_stage_{candidate_id}_{job_id}",
    )

    rejection_reason = ""

    if status in {
        "rejected_before_interview",
        "rejected_after_interview",
    }:
        rejection_reason = st.text_area(
            "Rejection reason",
            value=outcome.get(
                "rejection_reason",
                "",
            ),
            placeholder=(
                "What reason did the company give, "
                "if any?"
            ),
            key=(
                f"outcome_rejection_"
                f"{candidate_id}_{job_id}"
            ),
        )

    recruiter_feedback = st.text_area(
        "Recruiter / company feedback",
        value=outcome.get(
            "recruiter_feedback",
            "",
        ),
        placeholder=(
            "Paste or summarize any feedback "
            "you received."
        ),
        key=(
            f"outcome_feedback_"
            f"{candidate_id}_{job_id}"
        ),
    )

    candidate_notes = st.text_area(
        "Your notes",
        value=outcome.get(
            "candidate_notes",
            "",
        ),
        placeholder=(
            "What happened? What stood out?"
        ),
        key=(
            f"outcome_notes_"
            f"{candidate_id}_{job_id}"
        ),
    )

    lessons_learned = st.text_area(
        "Lessons learned",
        value=outcome.get(
            "lessons_learned",
            "",
        ),
        placeholder=(
            "Anything you want the system to "
            "remember for future applications."
        ),
        key=(
            f"outcome_lessons_"
            f"{candidate_id}_{job_id}"
        ),
    )

    offer_salary = ""
    offer_currency = ""

    if status == "offer":
        offer_columns = st.columns(2)

        with offer_columns[0]:
            offer_salary = st.text_input(
                "Offer salary",
                value=outcome.get(
                    "offer_salary",
                    "",
                ),
                key=(
                    f"outcome_salary_"
                    f"{candidate_id}_{job_id}"
                ),
            )

        with offer_columns[1]:
            offer_currency = st.text_input(
                "Currency",
                value=outcome.get(
                    "offer_currency",
                    "",
                ),
                placeholder="EUR",
                key=(
                    f"outcome_currency_"
                    f"{candidate_id}_{job_id}"
                ),
            )

    if st.button(
        "Save outcome",
        key=f"save_outcome_{candidate_id}_{job_id}",
        use_container_width=True,
    ):
        save_candidate_application_outcome(
            candidate_id=candidate_id,
            job_id=job_id,
            final_status=status,
            interview_stage=interview_stage,
            rejection_reason=rejection_reason,
            recruiter_feedback=recruiter_feedback,
            candidate_notes=candidate_notes,
            offer_salary=offer_salary,
            offer_currency=offer_currency,
            lessons_learned=lessons_learned,
        )

        st.toast(
            "Application outcome saved."
        )


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

        if status == "in_process":
            interview_prep = analysis.get(
                "interview_prep"
            )

            if interview_prep:
                st.divider()
                st.subheader(
                    "Interview Preparation"
                )

                what_the_company_needs = (
                    interview_prep.get(
                        "what_the_company_needs",
                        "",
                    )
                )

                if what_the_company_needs:
                    st.markdown(
                        "**What the company needs**"
                    )
                    st.write(
                        what_the_company_needs
                    )

                what_you_should_demonstrate = (
                    interview_prep.get(
                        "what_you_should_demonstrate",
                        [],
                    )
                )

                if what_you_should_demonstrate:
                    render_list(
                        "What you should demonstrate",
                        what_you_should_demonstrate,
                    )

                strongest_evidence = (
                    interview_prep.get(
                        "strongest_evidence",
                        [],
                    )
                )

                if strongest_evidence:
                    render_list(
                        "Your strongest evidence",
                        strongest_evidence,
                    )

                points_to_be_careful_with = (
                    interview_prep.get(
                        "points_to_be_careful_with",
                        [],
                    )
                )

                if points_to_be_careful_with:
                    render_list(
                        "Points to be careful with",
                        points_to_be_careful_with,
                    )

                likely_interview_topics = (
                    interview_prep.get(
                        "likely_interview_topics",
                        [],
                    )
                )

                if likely_interview_topics:
                    render_list(
                        "Likely interview topics",
                        likely_interview_topics,
                    )

                positioning = interview_prep.get(
                    "positioning",
                    "",
                )

                if positioning:
                    render_text_section(
                        "Your positioning",
                        positioning,
                        "No positioning guidance available.",
                    )

        st.divider()

        render_status_buttons(
            candidate_id=candidate_id,
            job_id=job_id,
            current_status=status,
        )

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
        page_title="JobHunter",
        page_icon="🎯",
        layout="wide",
    )

    initialize_database()

    current_user = require_login()
    render_logout_button()

    candidate_repository = CandidateRepository()

    st.title("JobHunter")

    st.caption(
        "Review opportunities and track your applications."
    )

    if current_user.access_level == "admin":
        candidates = candidate_repository.list_all()

        if not candidates:
            st.warning(
                "No candidates were found in the database."
            )
            return

        candidate_options = {
            candidate.name: candidate.id
            for candidate in candidates
        }

        selected_candidate_name = st.selectbox(
            "Candidate",
            options=list(candidate_options.keys()),
        )

        selected_candidate_id = candidate_options[
            selected_candidate_name
        ]

    else:
        if not current_user.candidate_id:
            st.warning(
                "Your account does not have a professional profile yet."
            )
            return

        selected_candidate_id = current_user.candidate_id

        candidate = candidate_repository.get(
            selected_candidate_id
        )

        if candidate is None:
            st.warning(
                "Your professional profile could not be found."
            )
            return

    counts = count_candidate_jobs_by_status(
        selected_candidate_id
    )

    rejected_total = (
        counts["rejected_before_interview"]
        + counts["rejected_after_interview"]
    )

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Applied",
        counts["applied"],
    )

    metric_columns[1].metric(
        "In process",
        counts["in_process"],
    )

    metric_columns[2].metric(
        "Rejected",
        rejected_total,
    )

    metric_columns[3].metric(
        "Offers",
        counts["offer"],
    )

    st.divider()

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