import logging

logger = logging.getLogger(__name__)

import streamlit as st

from components.job_analysis_view import render_job_analysis


from services.job_search_repository import JobSearchRepository
from services.session_auth import require_login, render_logout_button
from services.candidate_repository import CandidateRepository
from services.career_objective_repository import CareerObjectiveRepository
from services.career_update_repository import CareerUpdateRepository
from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
    ANALYSIS_VERSION,
    build_candidate_signature,
)
from services.cv_renderer import (
    render_tailored_cv_docx,
    render_tailored_cv_pdf,
)
from services.market_position_service import (
    build_market_position,
)

from services.ai_usage_budget import AIUsageBudget

from services.database import (
    ensure_candidate_job_analysis,
    list_candidate_jobs,
    update_candidate_job_notes,
    update_candidate_job_status,
)


st.set_page_config(
    page_title="Opportunities",
    page_icon="ðŸ”Ž",
    layout="wide",
)

st.title("Opportunities")

current_user = require_login()
render_logout_button()

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

career_objective = (
    CareerObjectiveRepository()
    .get_active(candidate_id)
)

career_updates = (
    CareerUpdateRepository()
    .list_for_candidate(candidate_id)
)

candidate_signature = build_candidate_signature(
    candidate,
    career_objective,
    career_updates,
)


OPPORTUNITY_TARGETS = {
    "Quick - 5 opportunities": 5,
    "Standard - 10 opportunities": 10,
    "Deep - 15 opportunities": 15,
}

INTERNAL_SCREENING_BATCH = 20


def empty_scan_result() -> dict:
    return {
        "selected": 0,
        "analyzed": 0,
        "hard_rejected": 0,
        "ai_eligible": 0,
        "ai_analyses_created": 0,
        "ai_approved": 0,
        "ai_rejected": 0,
        "best_match": 0,
        "potential": 0,
        "good_opportunity": 0,
        "opportunities_found": 0,
        "target_reached": False,
        "usage_limit_reached": False,
        "provider_quota_exhausted": False,
        "descriptions_reused": 0,
        "descriptions_fetched": 0,
        "descriptions_failed": 0,
        "failed": 0,
        "errors": [],
        "batch_market_signals": [],
        "batch_ai_job_ids": [],
    }


def merge_scan_result(
    total: dict,
    batch: dict,
) -> None:
    numeric_keys = (
        "selected",
        "analyzed",
        "hard_rejected",
        "ai_eligible",
        "ai_analyses_created",
        "ai_approved",
        "ai_rejected",
        "best_match",
        "potential",
        "good_opportunity",
        "opportunities_found",
        "descriptions_reused",
        "descriptions_fetched",
        "descriptions_failed",
        "failed",
    )

    for key in numeric_keys:
        total[key] = (
            total.get(key, 0)
            + batch.get(key, 0)
        )

    total["errors"].extend(
        batch.get(
            "errors",
            [],
        )
    )

    total["batch_market_signals"].extend(
        batch.get(
            "batch_market_signals",
            [],
        )
    )

    total["batch_ai_job_ids"].extend(
        batch.get(
            "batch_ai_job_ids",
            [],
        )
    )

    total["usage_limit_reached"] = (
        total.get(
            "usage_limit_reached",
            False,
        )
        or batch.get(
            "usage_limit_reached",
            False,
        )
    )

    total["provider_quota_exhausted"] = (
        total.get(
            "provider_quota_exhausted",
            False,
        )
        or batch.get(
            "provider_quota_exhausted",
            False,
        )
    )


if "scan_in_progress" not in st.session_state:
    st.session_state["scan_in_progress"] = False

if "scan_requested" not in st.session_state:
    st.session_state["scan_requested"] = False


def request_opportunity_scan() -> None:
    st.session_state["scan_requested"] = True
    st.session_state["scan_in_progress"] = True


pool_available = (
    repository
    .count_jobs_to_analyze_for_candidate(
        candidate_id=candidate_id,
        analysis_version=ANALYSIS_VERSION,
        candidate_signature=candidate_signature,
    )
)

st.caption(
    f"{pool_available} job(s) currently available to screen."
)

target_label = st.selectbox(
    "How many opportunities would you like me to find?",
    list(
        OPPORTUNITY_TARGETS.keys()
    ),
    index=1,
    disabled=st.session_state[
        "scan_in_progress"
    ],
)

target_opportunities = (
    OPPORTUNITY_TARGETS[
        target_label
    ]
)


st.button(
    (
        "Searching for opportunities..."
        if st.session_state["scan_in_progress"]
        else "Find opportunities for me"
    ),
    type="primary",
    use_container_width=True,
    disabled=st.session_state[
        "scan_in_progress"
    ],
    on_click=request_opportunity_scan,
)


if st.session_state["scan_in_progress"]:
    st.info(
        "I'm working through the available jobs now. "
        "This can take a few minutes, especially when there are "
        "many roles to screen. Please keep this page open and "
        "don't refresh it while the search is running. "
        "If you fancy one, this is a good time to grab a coffee "
        "or a cup of tea - I'll keep working here."
    )


if st.session_state.pop(
    "scan_requested",
    False,
):
    aggregate = empty_scan_result()

    # Unlimited for now.
    #
    # Later this comes from the user's subscription
    # allowance and/or extra analysis credits.
    ai_budget = (
        AIUsageBudget.unlimited()
    )

    links_created = 0

    try:
        while (
            aggregate["opportunities_found"]
            < target_opportunities
        ):
            jobs = (
                repository
                .list_jobs_to_analyze_for_candidate(
                    candidate_id=candidate_id,
                    analysis_version=ANALYSIS_VERSION,
                    candidate_signature=candidate_signature,
                    limit=INTERNAL_SCREENING_BATCH,
                )
            )

            if not jobs:
                break

            for job in jobs:
                created = (
                    ensure_candidate_job_analysis(
                        candidate_id=candidate_id,
                        job_id=job["id"],
                    )
                )

                if created:
                    links_created += 1

            remaining_target = (
                target_opportunities
                - aggregate[
                    "opportunities_found"
                ]
            )

            with st.spinner(
                "Screening jobs and looking for "
                "relevant opportunities..."
            ):
                batch_result = (
                    analysis_service.analyze_pending(
                        candidate_id=candidate_id,
                        limit=len(jobs),
                        target_opportunities=(
                            remaining_target
                        ),
                        ai_budget=ai_budget,
                    )
                )

            merge_scan_result(
                aggregate,
                batch_result,
            )

            if (
                batch_result.get(
                    "usage_limit_reached",
                    False,
                )
                or batch_result.get(
                    "provider_quota_exhausted",
                    False,
                )
            ):
                break

            # Avoid an endless loop if nothing in the
            # selected batch can be persisted/analyzed.
            if (
                batch_result.get(
                    "analyzed",
                    0,
                ) == 0
            ):
                break

        aggregate[
            "opportunities_found"
        ] = aggregate[
            "ai_approved"
        ]

        aggregate[
            "target_reached"
        ] = (
            aggregate[
                "opportunities_found"
            ]
            >= target_opportunities
        )

        pool_remaining = (
            repository
            .count_jobs_to_analyze_for_candidate(
                candidate_id=candidate_id,
                analysis_version=ANALYSIS_VERSION,
                candidate_signature=candidate_signature,
            )
        )

        st.session_state[
            "last_scan_result"
        ] = aggregate

        st.session_state[
            "last_scan_total"
        ] = aggregate[
            "selected"
        ]

        st.session_state[
            "last_links_created"
        ] = links_created

        st.session_state[
            "last_scan_target"
        ] = target_opportunities

        st.session_state[
            "last_pool_remaining"
        ] = pool_remaining

    except Exception:
        st.session_state[
            "scan_in_progress"
        ] = False

        raise

    st.session_state[
        "scan_in_progress"
    ] = False

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

    target_requested = st.session_state.get(
        "last_scan_target",
        0,
    )

    pool_remaining = st.session_state.get(
        "last_pool_remaining",
        0,
    )

    opportunities_found = scan_result.get(
        "ai_approved",
        0,
    )

    hard_rejected = scan_result.get(
        "hard_rejected",
        0,
    )

    ai_analyzed = scan_result.get(
        "ai_analyses_created",
        0,
    )

    if (
        target_requested
        and opportunities_found >= target_requested
    ):
        st.success(
            f"I found {opportunities_found} relevant opportunities "
            f"for you after reviewing {total_scanned} jobs."
        )

    elif pool_remaining == 0:
        st.info(
            f"I found {opportunities_found} relevant opportunities. "
            "I've now worked through everything currently available "
            "in the pool."
        )

    else:
        st.info(
            f"I found {opportunities_found} relevant opportunities "
            f"so far after reviewing {total_scanned} jobs."
        )

    st.caption(
        f"Of those, {hard_rejected} were ruled out before the "
        f"candidate-specific AI comparison, while {ai_analyzed} "
        f"needed a deeper analysis. "
        f"There are {pool_remaining} jobs left to screen."
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
        "Competitive",
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

    detail_col1, detail_col2 = st.columns(2)

    detail_col1.metric(
        "Hard Rejected",
        scan_result.get(
            "hard_rejected",
            0,
        ),
    )

    detail_col2.metric(
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


# =========================================================
# Market Position
# =========================================================

if scan_result:
    market_position = build_market_position(
        candidate_id=candidate_id,
        batch_signals=scan_result.get(
            "batch_market_signals",
            [],
        ),
    )

    current_market = market_position.get(
        "current_batch",
        {},
    )

    historical_market = market_position.get(
        "historical",
        {},
    )

    current_sample = current_market.get(
        "sample_size",
        0,
    )

    historical_sample = historical_market.get(
        "sample_size",
        0,
    )

    current_role_families = current_market.get(
        "role_families",
        [],
    )

    historical_role_families = historical_market.get(
        "role_families",
        [],
    )

    current_blockers = current_market.get(
        "best_match_blockers",
        [],
    )

    historical_blockers = historical_market.get(
        "best_match_blockers",
        [],
    )

    current_raise_fit = current_market.get(
        "what_would_raise_fit",
        [],
    )

    recurring_gaps = historical_market.get(
        "what_would_raise_fit",
        [],
    )


    def labels(
        items,
        limit=3,
    ) -> list[str]:
        return [
            str(item.get("label", "")).strip()
            for item in (items or [])[:limit]
            if str(item.get("label", "")).strip()
        ]


    def natural_join(
        values: list[str],
    ) -> str:
        values = [
            value
            for value in values
            if value
        ]

        if not values:
            return ""

        if len(values) == 1:
            return values[0]

        if len(values) == 2:
            return (
                values[0]
                + " and "
                + values[1]
            )

        return (
            ", ".join(values[:-1])
            + ", and "
            + values[-1]
        )


    st.divider()
    st.subheader("Market Position")

    st.caption(
        f"This reading uses {current_sample} jobs from this search "
        f"and {historical_sample} jobs from your previous market signal."
    )

    # -----------------------------------------------------
    # Current reading
    # -----------------------------------------------------

    st.markdown("### What this search is telling me")

    if current_role_families:
        strongest_current = (
            current_role_families[0]["label"]
        )

        st.write(
            "The clearest signal from this search is around "
            f"**{strongest_current}**. "
            "That does not mean you should change direction toward "
            "every role in that family; it tells us where your current "
            "evidence is getting the strongest response."
        )

    blocker_labels = labels(
        current_blockers,
        3,
    )

    if blocker_labels:
        st.write(
            "The main things keeping some roles from becoming stronger "
            "matches are "
            f"**{natural_join(blocker_labels)}**."
        )

        st.write(
            "I would treat these as market signals, not automatically "
            "as things you need to learn. Some may simply belong to "
            "roles that are adjacent to, rather than central to, your "
            "career direction."
        )

    # -----------------------------------------------------
    # Traction
    # -----------------------------------------------------

    st.markdown("### Where you're getting traction")

    current_families = labels(
        current_role_families,
        4,
    )

    historical_families = labels(
        historical_role_families,
        4,
    )

    if current_families:
        st.write(
            "In this search, your profile is showing the most "
            "competitiveness around "
            f"**{natural_join(current_families)}**."
        )

    if historical_families:
        st.write(
            "Looking across previous searches as well, the recurring "
            "direction has been "
            f"**{natural_join(historical_families)}**."
        )

    # -----------------------------------------------------
    # What raises fit
    # -----------------------------------------------------

    st.markdown("### What could improve your chances")

    short_term = labels(
        current_raise_fit,
        4,
    )

    persistent = labels(
        recurring_gaps,
        4,
    )

    if short_term:
        st.write(
            "For the roles in this particular search, stronger evidence "
            "around "
            f"**{natural_join(short_term)}** "
            "would have increased your fit."
        )

    if persistent:
        st.write(
            "Across the broader history, the areas that keep appearing "
            "are "
            f"**{natural_join(persistent)}**."
        )

        st.write(
            "The Career Development section will help decide which of "
            "those are actually worth investing in, rather than treating "
            "every recurring requirement as a development priority."
        )

    if (
        not current_role_families
        and not current_blockers
        and not current_raise_fit
    ):
        st.write(
            "There isn't enough consistent evidence in this batch yet "
            "to make a useful market reading."
        )


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


def clean_display_bullet(value: str) -> str:
    text = str(value or "").strip()

    while text.startswith(("-", "*", "?")):
        text = text[1:].strip()

    return text


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

    return "_".join(parts) + ".docx"


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
                    clean_bullet = clean_display_bullet(
                        bullet
                    )

                    if clean_bullet:
                        st.markdown(
                            f"- {clean_bullet}"
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
                clean_item = clean_display_bullet(
                    item
                )

                if clean_item:
                    st.markdown(
                        f"- {clean_item}"
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
        "Competitive "
        f"({len(good_opportunities)})"
    ):
        if not good_opportunities:
            st.info(
                "No competitive opportunities found."
            )

        for job in good_opportunities:
            render_job(job)

elif scan_result:
    st.info(
        "No competitive opportunities were found "
        "in this scan."
    )
