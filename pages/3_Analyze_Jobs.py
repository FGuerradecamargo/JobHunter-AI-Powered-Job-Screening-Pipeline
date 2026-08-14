import streamlit as st

from services.job_search_repository import JobSearchRepository
from services.session_auth import require_login
from services.candidate_repository import CandidateRepository
from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
)
from services.database import (
    ensure_candidate_job_analysis,
    list_candidate_jobs,
)


st.set_page_config(
    page_title="Analyze Jobs",
    page_icon="🔎",
    layout="wide",
)

st.title("Analyze Jobs")

current_user = require_login()

repository = JobSearchRepository()
candidate_repository = CandidateRepository()
analysis_service = CandidateJobAnalysisService()


if not current_user.candidate_id:
    st.error(
        "Your account does not have a professional profile."
    )
    st.stop()


candidate_id = current_user.candidate_id

candidate = candidate_repository.get(
    candidate_id
)

if candidate is None:
    st.error(
        "Could not load your professional profile."
    )
    st.stop()


st.write(
    "JobHunter will scan available jobs and compare them "
    "with your professional profile, career direction, "
    "preferences, constraints and current priorities."
)


source = st.radio(
    "Job source",
    [
        "My jobs",
        "Global jobs",
    ],
    horizontal=True,
)


limit = st.selectbox(
    "Maximum jobs to scan",
    [
        25,
        50,
        100,
        200,
    ],
    index=1,
)


if st.button(
    "Find opportunities for me",
    type="primary",
    use_container_width=True,
):
    if source == "My jobs":
        jobs = repository.list_user_jobs(
            user_id=current_user.id,
            limit=limit,
        )
    else:
        jobs = repository.list_global_jobs(
            limit=limit,
        )

    links_created = 0

    for job in jobs:
        created = ensure_candidate_job_analysis(
            candidate_id=candidate_id,
            job_id=job["id"],
        )

        if created:
            links_created += 1

    with st.spinner(
        "Scanning and analyzing opportunities..."
    ):
        result = analysis_service.analyze_pending(
            candidate_id=candidate_id,
            limit=len(jobs),
        )

    st.session_state["last_scan_result"] = result
    st.session_state["last_scan_total"] = len(jobs)
    st.session_state["last_links_created"] = links_created

    st.rerun()


scan_result = st.session_state.get(
    "last_scan_result"
)

if scan_result:
    st.divider()

    total_scanned = st.session_state.get(
        "last_scan_total",
        0,
    )

    st.caption(
        f"{total_scanned} jobs scanned."
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Best Matches",
        scan_result.get(
            "best_match",
            0,
        ),
    )

    col2.metric(
        "Trade-offs",
        scan_result.get(
            "tradeoff",
            0,
        ),
    )

    col3.metric(
        "Lower Alignment",
        scan_result.get(
            "lower_alignment",
            0,
        ),
    )


review_jobs = list_candidate_jobs(
    candidate_id=candidate_id,
    status="in_review",
)


best_matches = []
tradeoffs = []
lower_alignment = []

for job in review_jobs:
    analysis = job.get(
        "analysis",
        {},
    )

    bucket = analysis.get(
        "bucket"
    )

    if bucket == "best_match":
        best_matches.append(job)

    elif bucket == "tradeoff":
        tradeoffs.append(job)

    elif bucket == "lower_alignment":
        lower_alignment.append(job)


def render_job(
    job: dict,
) -> None:
    analysis = job.get(
        "analysis",
        {},
    )

    title = job.get(
        "title",
    ) or "Untitled role"

    company = job.get(
        "company",
    ) or "Unknown company"

    with st.expander(
        f"{title} - {company}"
    ):
        simple_summary = analysis.get(
            "simple_summary",
            "",
        )

        simple_recommendation = analysis.get(
            "simple_recommendation",
            "",
        )

        if simple_recommendation:
            st.markdown(
                f"**{simple_recommendation}**"
            )

        if simple_summary:
            st.write(
                simple_summary
            )

        location = job.get(
            "location"
        )

        if location:
            st.caption(
                f"Location: {location}"
            )

        direction = analysis.get(
            "direction_alignment"
        )

        competitive = analysis.get(
            "competitive_status"
        )

        if direction:
            st.write(
                f"Career alignment: {direction}"
            )

        if competitive:
            st.write(
                f"Competitive status: {competitive}"
            )

        priority_matches = analysis.get(
            "priority_matches",
            [],
        )

        if priority_matches:
            st.write(
                "Priority matches:"
            )

            for item in priority_matches:
                st.write(
                    f"- {item}"
                )

        priority_conflicts = analysis.get(
            "priority_conflicts",
            [],
        )

        personal_negatives = analysis.get(
            "personal_negatives",
            [],
        )

        tradeoff_items = (
            priority_conflicts
            + personal_negatives
        )

        if tradeoff_items:
            st.write(
                "Trade-offs:"
            )

            for item in tradeoff_items:
                st.write(
                    f"- {item}"
                )

        development_gaps = analysis.get(
            "development_gaps",
            [],
        )

        structural_gaps = analysis.get(
            "structural_gaps",
            [],
        )

        if development_gaps or structural_gaps:
            with st.expander(
                "Technical analysis"
            ):
                if development_gaps:
                    st.write(
                        "Development gaps:"
                    )

                    for item in development_gaps:
                        st.write(
                            f"- {item}"
                        )

                if structural_gaps:
                    st.write(
                        "Structural gaps:"
                    )

                    for item in structural_gaps:
                        st.write(
                            f"- {item}"
                        )

        url = job.get(
            "url"
        )

        if url:
            st.link_button(
                "Open job",
                url,
            )


if (
    best_matches
    or tradeoffs
    or lower_alignment
):
    st.divider()

    with st.expander(
        f"Best Matches ({len(best_matches)})",
        expanded=True,
    ):
        if not best_matches:
            st.info(
                "No best matches found in this scan."
            )

        for job in best_matches:
            render_job(job)

    with st.expander(
        "Good Opportunities with Trade-offs "
        f"({len(tradeoffs)})"
    ):
        if not tradeoffs:
            st.info(
                "No trade-off opportunities found."
            )

        for job in tradeoffs:
            render_job(job)

    with st.expander(
        "Competitive but Lower Alignment "
        f"({len(lower_alignment)})"
    ):
        if not lower_alignment:
            st.info(
                "No lower-alignment opportunities found."
            )

        for job in lower_alignment:
            render_job(job)

elif scan_result:
    st.info(
        "No competitive opportunities were found "
        "in this scan."
    )
