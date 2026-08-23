import logging
import os
import hashlib
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

import streamlit as st

from components.job_analysis_view import render_job_analysis

from models.job import Job

from services.job_search_repository import JobSearchRepository
from services.job_source_repository import JobSourceRepository
from services.session_auth import require_login, render_logout_button
from services.candidate_repository import CandidateRepository
from services.gmail_connection_repository import GmailConnectionRepository
from services.gmail_message_repository import GmailMessageRepository
from services.gmail_job_processor import GmailJobProcessor
from services.gmail_sync_service import GmailSyncService
from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
    ANALYSIS_VERSION,
    build_candidate_signature,
)
from services.cv_renderer import (
    render_tailored_cv_docx,
    render_tailored_cv_pdf,
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
    page_icon="ðŸ”Ž",
    layout="wide",
)

st.title("Analyze Jobs")

current_user = require_login()
render_logout_button()

repository = JobSearchRepository()
job_source_repository = JobSourceRepository()
candidate_repository = CandidateRepository()
analysis_service = CandidateJobAnalysisService()

gmail_repository = GmailConnectionRepository()
gmail_message_repository = GmailMessageRepository()

gmail_job_processor = GmailJobProcessor(
    gmail_message_repository=gmail_message_repository
)


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


gmail_connection = gmail_repository.get_by_user_id(
    current_user.id
)

if gmail_connection is not None:
    with st.expander(
        "Gmail job source",
        expanded=False,
    ):
        st.caption(
            f"Connected: {gmail_connection.gmail_address}"
        )

        if gmail_connection.last_sync_at:
            st.caption(
                f"Last sync: {gmail_connection.last_sync_at}"
            )

        if st.button(
            "Sync Gmail",
            type="secondary",
            use_container_width=True,
            key="analyze_jobs_sync_gmail",
        ):
            try:
                gmail_sync_service = GmailSyncService(
                    client_id=os.environ[
                        "GOOGLE_OAUTH_CLIENT_ID"
                    ],
                    client_secret=os.environ[
                        "GOOGLE_OAUTH_CLIENT_SECRET"
                    ],
                    gmail_connection_repository=(
                        gmail_repository
                    ),
                    gmail_message_repository=(
                        gmail_message_repository
                    ),
                )

                with st.spinner(
                    "Syncing Gmail and adding new jobs "
                    "to the job pool..."
                ):
                    sync_result = (
                        gmail_sync_service
                        .sync_recent_job_alerts(
                            user_id=current_user.id
                        )
                    )

                    processing_result = (
                        gmail_job_processor
                        .process_pending_messages(
                            user_id=current_user.id,
                            candidate_id=candidate_id,
                            limit=100,
                        )
                    )

                st.success(
                    "Gmail sync completed. "
                    "New jobs are ready for analysis."
                )

                sync_columns = st.columns(4)

                sync_columns[0].metric(
                    "Emails found",
                    sync_result.total_messages_found,
                )

                sync_columns[1].metric(
                    "New emails",
                    sync_result.new_messages_found,
                )

                sync_columns[2].metric(
                    "Jobs added",
                    processing_result.jobs_created,
                )

                sync_columns[3].metric(
                    "Already known",
                    processing_result.jobs_unchanged,
                )

            except Exception as error:
                st.error(
                    "Could not synchronize Gmail."
                )
                logger.exception("Could not synchronize Gmail.")

else:
    st.caption(
        "Gmail is not connected. "
        "You can connect it from Connect Gmail."
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
            "matcher_review": 0,
            "ai_analyses_created": 0,
            "ai_approved": 0,
            "ai_rejected": 0,
            "best_match": 0,
            "tradeoff": 0,
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

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Best Matches",
        scan_result.get(
            "best_match",
            0,
        ),
    )

    col2.metric(
        "Good Opportunities",
        scan_result.get(
            "good_opportunity",
            0,
        ),
    )

    col3.metric(
        "Potential",
        scan_result.get(
            "potential",
            0,
        ),
    )

    col4.metric(
        "AI Analyzed",
        scan_result.get(
            "ai_analyses_created",
            0,
        ),
    )

    detail_col1, detail_col2, detail_col3 = (
        st.columns(3)
    )

    detail_col1.metric(
        "Matcher Rejected",
        scan_result.get(
            "matcher_rejected",
            0,
        ),
    )

    detail_col2.metric(
        "Hard Rejected",
        scan_result.get(
            "hard_rejected",
            0,
        ),
    )

    detail_col3.metric(
        "AI Rejected",
        scan_result.get(
            "ai_rejected",
            0,
        ),
    )

    failed = scan_result.get(
        "failed",
        0,
    )

    if failed:
        st.warning(
            f"{failed} job(s) failed during analysis."
        )

        for error in scan_result.get("errors", []):
            st.code(str(error))


review_jobs = list_candidate_jobs(
    candidate_id=candidate_id,
    status="in_review",
)


best_matches = []
potential_jobs = []
good_opportunities = []

for job in review_jobs:
    analysis = job.get(
        "analysis",
        {},
    )

    bucket = (
        analysis.get("bucket")
        or analysis.get("recommendation")
    )

    if bucket == "best_match":
        best_matches.append(job)

    elif bucket == "potential":
        potential_jobs.append(job)

    elif bucket == "good_opportunity":
        good_opportunities.append(job)


def build_cv_filename(
    candidate_name: str,
    company: str,
    title: str,
) -> str:
    def clean(value: str) -> str:
        value = value.strip()

        safe = "".join(
            character
            if character.isalnum()
            else "_"
            for character in value
        )

        while "__" in safe:
            safe = safe.replace(
                "__",
                "_",
            )

        return safe.strip("_")

    parts = [
        clean(candidate_name),
        clean(company),
        clean(title),
        "CV",
    ]

    parts = [
        part
        for part in parts
        if part
    ]

    return "_".join(parts)


def render_tailored_cv(
    analysis: dict,
    candidate_name: str,
    company: str,
    title: str,
) -> None:
    tailored_cv = analysis.get(
        "tailored_cv"
    )

    if not tailored_cv:
        return

    with st.expander("Tailored CV"):
        headline = tailored_cv.get(
            "headline",
            "",
        )

        if headline:
            st.markdown(
                f"### {headline}"
            )

        professional_summary = (
            tailored_cv.get(
                "professional_summary",
                "",
            )
        )

        if professional_summary:
            st.subheader(
                "Professional Summary"
            )
            st.write(
                professional_summary
            )

        key_skills = tailored_cv.get(
            "key_skills",
            [],
        )

        if key_skills:
            st.subheader(
                "Key Skills"
            )

            for skill in key_skills:
                st.write(
                    f"- {skill}"
                )

        experiences = tailored_cv.get(
            "experiences",
            [],
        )

        if experiences:
            st.subheader(
                "Relevant Experience"
            )

            for experience in experiences:
                role = experience.get(
                    "role",
                    "",
                )

                company_name = (
                    experience.get(
                        "company",
                        "",
                    )
                )

                heading_parts = [
                    value
                    for value in [
                        role,
                        company_name,
                    ]
                    if value
                ]

                if heading_parts:
                    st.markdown(
                        "**"
                        + " - ".join(
                            heading_parts
                        )
                        + "**"
                    )

                for bullet in experience.get(
                    "tailored_bullets",
                    [],
                ):
                    st.write(
                        f"- {bullet}"
                    )

        additional_information = (
            tailored_cv.get(
                "additional_relevant_information",
                [],
            )
        )

        if additional_information:
            st.subheader(
                "Additional Relevant Information"
            )

            for item in additional_information:
                st.write(
                    f"- {item}"
                )

        docx_data = render_tailored_cv_docx(
            candidate_name=candidate_name,
            tailored_cv=tailored_cv,
        )

        pdf_data = render_tailored_cv_pdf(
            candidate_name=candidate_name,
            tailored_cv=tailored_cv,
        )

        docx_filename = build_cv_filename(
            candidate_name=candidate_name,
            company=company,
            title=title,
        )

        pdf_filename = (
            docx_filename.removesuffix(".docx")
            + ".pdf"
        )

        download_columns = st.columns(2)

        with download_columns[0]:
            st.download_button(
                "Download CV (.docx)",
                data=docx_data,
                file_name=docx_filename,
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                use_container_width=True,
            )

        with download_columns[1]:
            st.download_button(
                "Download CV (.pdf)",
                data=pdf_data,
                file_name=pdf_filename,
                mime="application/pdf",
                use_container_width=True,
            )



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
        render_job_analysis(
            job,
        )

        render_tailored_cv(
            analysis=analysis,
            candidate_name=candidate.name,
            company=company,
            title=title,
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
    or potential_jobs
    or good_opportunities
):
    st.divider()

    with st.expander(
        f"Best Matches ({len(best_matches)})",
        expanded=True,
    ):
        if not best_matches:
            st.info(
                "No best matches found."
            )

        for job in best_matches:
            render_job(job)

    with st.expander(
        f"Potential ({len(potential_jobs)})",
        expanded=(
            not best_matches
            and bool(potential_jobs)
        ),
    ):
        if not potential_jobs:
            st.info(
                "No potential opportunities found."
            )

        for job in potential_jobs:
            render_job(job)

    with st.expander(
        "Good Opportunities "
        f"({len(good_opportunities)})"
    ):
        if not good_opportunities:
            st.info(
                "No good opportunities found."
            )

        for job in good_opportunities:
            render_job(job)

elif scan_result:
    st.info(
        "No competitive opportunities were found "
        "in this scan."
    )


