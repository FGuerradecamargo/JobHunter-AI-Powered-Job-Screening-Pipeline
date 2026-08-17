import streamlit as st

from services.candidate_repository import CandidateRepository
from services.session_auth import require_login, render_logout_button
from services.database import (
    count_candidate_jobs_by_status,
    initialize_database,
    list_candidate_jobs,
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

        recommendation = (
                item.get("recommendation")
                or "not_analyzed"
        )

        metric_columns = st.columns(4)

        metric_columns[0].metric(
            "Current fit",
            current_fit,
        )

        metric_columns[1].metric(
            "Growth value",
            growth_value,
        )

        metric_columns[2].metric(
            "Recommendation",
            recommendation
            .replace("_", " ")
            .title(),
        )

        metric_columns[3].metric(
            "Status",
            STATUS_LABELS.get(
                status,
                status,
            ),
        )

        st.write(
            f"**Location:** {location}"
        )

        render_text_section(
            "Quick overview",
            simple_summary,
            (
                "A simple overview is not available for this analysis yet. "
                "Open the technical details below."
            ),
        )

        render_text_section(
            "My recommendation",
            simple_recommendation,
            final_recommendation or "No recommendation available.",
        )

        with st.expander(
                "View technical details",
                expanded=False,
        ):
            first_row = st.columns(2)

            with first_row[0]:
                render_list(
                    "What you already bring",
                    requirements_met,
                )

            with first_row[1]:
                render_list(
                    "Main gaps",
                    all_gaps,
                )

            st.divider()

            second_row = st.columns(2)

            with second_row[0]:
                render_list(
                    "Positive points",
                    positive_points,
                )

            with second_row[1]:
                render_list(
                    "Personal tradeoffs",
                    personal_tradeoffs,
                )

            st.divider()

            render_text_section(
                "Why this role may be worth considering",
                reason,
                "No explanation available.",
            )

            render_text_section(
                "Full recommendation",
                final_recommendation,
                "No full recommendation available.",
            )

        st.divider()

        render_status_buttons(
            candidate_id=candidate_id,
            job_id=job_id,
            current_status=status,
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

    metric_columns = st.columns(5)

    metric_columns[0].metric(
        "In review",
        counts["in_review"],
    )

    metric_columns[1].metric(
        "Applied",
        counts["applied"],
    )

    metric_columns[2].metric(
        "In process",
        counts["in_process"],
    )

    metric_columns[3].metric(
        "Rejected by company",
        (
                counts["rejected_before_interview"]
                + counts["rejected_after_interview"]
        ),
    )

    metric_columns[4].metric(
        "Offers",
        counts["offer"],
    )

    st.divider()

    tabs = st.tabs(
        [
            f"In review ({counts['in_review']})",
            f"Not applied ({counts['user_rejected']})",
            f"Applied ({counts['applied']})",
            f"In process ({counts['in_process']})",
            (
                "Rejected before interview "
                f"({counts['rejected_before_interview']})"
            ),
            (
                "Rejected in process "
                f"({counts['rejected_after_interview']})"
            ),
            f"Offers ({counts['offer']})",
            f"System rejected ({counts['system_rejected']})",
        ]
    )

    with tabs[0]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="in_review",
        )

    with tabs[1]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="user_rejected",
        )

    with tabs[2]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="applied",
        )

    with tabs[3]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="in_process",
        )

    with tabs[4]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="rejected_before_interview",
        )

    with tabs[5]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="rejected_after_interview",
        )

    with tabs[6]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="offer",
        )

    with tabs[7]:
        render_job_section(
            candidate_id=selected_candidate_id,
            status="system_rejected",
        )


if __name__ == "__main__":
    main()