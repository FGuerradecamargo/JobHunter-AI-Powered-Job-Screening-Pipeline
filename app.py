import streamlit as st

from services.candidate_repository import CandidateRepository
from services.database import (
    count_candidate_jobs_by_status,
    initialize_database,
    list_candidate_jobs,
    update_candidate_job_notes,
    update_candidate_job_status,
)


STATUS_LABELS = {
    "in_review": "In review",
    "applied": "Applied",
    "in_process": "In process",
    "rejected": "Rejected",
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

    columns = st.columns(4)

    with columns[0]:
        if current_status != "in_review":
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

    with columns[1]:
        if current_status != "applied":
            if st.button(
                "Mark as Applied",
                key=f"applied_{candidate_id}_{job_id}",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "applied",
                )

    with columns[2]:
        if current_status != "in_process":
            if st.button(
                "Move to In process",
                key=f"in_process_{candidate_id}_{job_id}",
                type="primary",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "in_process",
                )

    with columns[3]:
        if current_status != "rejected":
            if st.button(
                "Mark as Rejected",
                key=f"rejected_{candidate_id}_{job_id}",
                use_container_width=True,
            ):
                change_status(
                    candidate_id,
                    job_id,
                    "rejected",
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

        third_row = st.columns(2)

        with third_row[0]:
            render_text_section(
                "Why this role is worth considering",
                reason,
                "No explanation available.",
            )

        with third_row[1]:
            render_text_section(
                "Final recommendation",
                final_recommendation,
                "No final recommendation available.",
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
                notes=notes,
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
        candidate_id,
        status,
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

    candidate_repository = CandidateRepository()
    candidates = candidate_repository.list_all()

    if not candidates:
        st.warning(
            "No candidates were found in the database."
        )
        return

    st.title("JobHunter")

    st.caption(
        "Review opportunities and track your applications."
    )

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

    counts = count_candidate_jobs_by_status(
        selected_candidate_id
    )

    summary_columns = st.columns(5)

    summary_columns[0].metric(
        "Total tracked",
        sum(counts.values()),
    )

    summary_columns[1].metric(
        "In review",
        counts["in_review"],
    )

    summary_columns[2].metric(
        "Applied",
        counts["applied"],
    )

    summary_columns[3].metric(
        "In process",
        counts["in_process"],
    )

    summary_columns[4].metric(
        "Rejected",
        counts["rejected"],
    )

    st.divider()

    (
        review_tab,
        applied_tab,
        process_tab,
        rejected_tab,
    ) = st.tabs(
        [
            f"In review ({counts['in_review']})",
            f"Applied ({counts['applied']})",
            f"In process ({counts['in_process']})",
            f"Rejected ({counts['rejected']})",
        ]
    )

    with review_tab:
        st.subheader("Jobs waiting for your decision")
        render_job_section(
            selected_candidate_id,
            "in_review",
        )

    with applied_tab:
        st.subheader("Applications in progress")
        render_job_section(
            selected_candidate_id,
            "applied",
        )

    with rejected_tab:
        st.subheader("Rejected or discarded opportunities")
        render_job_section(
            selected_candidate_id,
            "rejected",
        )

    with process_tab:
        st.subheader("Applications currently in process")
        render_job_section(
            selected_candidate_id,
            "in_process",
        )


if __name__ == "__main__":
    main()