import hashlib
from urllib.parse import urlparse

import streamlit as st

from models.job import Job

from services.job_search_repository import JobSearchRepository
from services.job_source_repository import JobSourceRepository
from services.session_auth import require_login, render_logout_button
from services.candidate_repository import CandidateRepository
from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
    ANALYSIS_VERSION,
    build_candidate_signature,
)
from services.database import (
    ensure_candidate_job_analysis,
    list_candidate_jobs,
    update_candidate_job_notes,
    update_candidate_job_status,
    upsert_raw_job,
)


st.set_page_config(
    page_title="Analyze Jobs",
    page_icon="🔎",
    layout="wide",
)

st.title("Analyze Jobs")

current_user = require_login()
render_logout_button()

repository = JobSearchRepository()
job_source_repository = JobSourceRepository()
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



st.divider()

with st.expander(
    "Add a job manually",
):
    st.caption(
        "Enter the complete job information. "
        "All fields are required."
    )

    with st.form(
        "manual_job_form",
        clear_on_submit=True,
    ):
        manual_title = st.text_input(
            "Job title *"
        )

        manual_company = st.text_input(
            "Company *"
        )

        manual_location = st.text_input(
            "Location *"
        )

        manual_description = st.text_area(
            "Job description *",
            height=250,
            placeholder=(
                "Paste the complete job description here."
            ),
        )

        manual_url = st.text_input(
            "Job URL *",
            placeholder="https://...",
        )

        manual_submit = st.form_submit_button(
            "Add job",
            type="primary",
            use_container_width=True,
        )

    if manual_submit:
        title = manual_title.strip()
        company = manual_company.strip()
        location = manual_location.strip()
        description = manual_description.strip()
        url = manual_url.strip()

        missing_fields = []

        if not title:
            missing_fields.append("Job title")

        if not company:
            missing_fields.append("Company")

        if not location:
            missing_fields.append("Location")

        if not description:
            missing_fields.append("Job description")

        if not url:
            missing_fields.append("Job URL")

        if missing_fields:
            st.error(
                "Complete all required fields: "
                + ", ".join(missing_fields)
                + "."
            )

        else:
            parsed_url = urlparse(url)

            valid_url = (
                parsed_url.scheme in {
                    "http",
                    "https",
                }
                and bool(parsed_url.netloc)
            )

            if not valid_url:
                st.error(
                    "Enter a valid job URL starting "
                    "with http:// or https://."
                )

            else:
                normalized_url = url.strip().lower()

                job_id = (
                    "manual_"
                    + hashlib.sha256(
                        normalized_url.encode(
                            "utf-8"
                        )
                    ).hexdigest()[:24]
                )

                raw_text = (
                    f"Title: {title}\n"
                    f"Company: {company}\n"
                    f"Location: {location}\n"
                    f"URL: {url}\n\n"
                    f"{description}"
                )

                manual_job = Job(
                    id=job_id,
                    raw_text=raw_text,
                    url=url,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                )

                upsert_raw_job(
                    manual_job
                )

                job_source_repository.add_source(
                    job_id=job_id,
                    user_id=current_user.id,
                    source_type="manual",
                )

                st.success(
                    "Job added to the global pool. "
                    "It will be considered in your next opportunity scan."
                )

                st.rerun()


st.divider()

candidate_signature = build_candidate_signature(
    candidate
)


limit = st.selectbox(
    "Maximum new jobs to analyze",
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
    jobs = repository.list_jobs_to_analyze_for_candidate(
        candidate_id=candidate_id,
        analysis_version=ANALYSIS_VERSION,
        candidate_signature=candidate_signature,
        limit=limit,
    )

    if not jobs:
        st.session_state["last_scan_result"] = {
            "selected": 0,
            "analyzed": 0,
            "hard_rejected": 0,
            "matcher_rejected": 0,
            "ai_analyses_created": 0,
            "ai_approved": 0,
            "ai_rejected": 0,
            "best_match": 0,
            "tradeoff": 0,
            "lower_alignment": 0,
            "failed": 0,
            "errors": [],
        }

        st.session_state["last_scan_total"] = 0
        st.session_state["last_links_created"] = 0

        st.rerun()

    links_created = 0

    for job in jobs:
        created = ensure_candidate_job_analysis(
            candidate_id=candidate_id,
            job_id=job["id"],
        )

        if created:
            links_created += 1

    with st.spinner(
        "Analyzing new opportunities from the global pool..."
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

        st.divider()

        job_id = str(
            job["id"]
        )

        st.markdown(
            "**Your notes**"
        )

        notes_value = st.text_area(
            "Personal notes",
            value=job.get(
                "notes",
                "",
            ),
            key=f"analysis_notes_{candidate_id}_{job_id}",
            label_visibility="collapsed",
            placeholder=(
                "Add anything useful for your decision: "
                "salary, concerns, questions, recruiter details..."
            ),
        )

        if st.button(
            "Save notes",
            key=f"save_analysis_notes_{candidate_id}_{job_id}",
            use_container_width=True,
        ):
            update_candidate_job_notes(
                candidate_id=candidate_id,
                job_id=job_id,
                notes=notes_value,
            )

            st.toast(
                "Notes saved."
            )

        st.markdown(
            "**Your decision**"
        )

        decision_columns = st.columns(2)

        with decision_columns[0]:
            if st.button(
                "Do not apply",
                key=f"analysis_reject_{candidate_id}_{job_id}",
                use_container_width=True,
            ):
                update_candidate_job_status(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    status="user_rejected",
                )

                st.rerun()

        with decision_columns[1]:
            if st.button(
                "Mark as Applied",
                key=f"analysis_apply_{candidate_id}_{job_id}",
                type="primary",
                use_container_width=True,
            ):
                update_candidate_job_status(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    status="applied",
                )

                st.rerun()

        url = job.get(
            "url"
        )

        if url:
            st.link_button(
                "Open job",
                url,
                use_container_width=True,
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
