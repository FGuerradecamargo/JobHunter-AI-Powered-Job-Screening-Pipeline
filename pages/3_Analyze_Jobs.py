import streamlit as st

from services.job_category_service import (
    JobCategoryService,
)
from services.job_search_repository import (
    JobSearchRepository,
)
from services.session_auth import require_login

from services.candidate_adapter import (
    candidate_to_profile,
)
from services.candidate_repository import (
    CandidateRepository,
)
from services.ai.openai_client import OpenAIClient
from services.ai.ai_recommendation_service import (
    AIRecommendationService,
)

from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
)
from services.database import (
    ensure_candidate_job_analysis,
)


st.set_page_config(
    page_title="Analyze Jobs",
    page_icon="🔎",
    layout="wide",
)

st.title("Analyze Jobs")

current_user = require_login()

repository = JobSearchRepository()
category_service = JobCategoryService()
candidate_repository = CandidateRepository()
analysis_service = CandidateJobAnalysisService()

recommendation_service = AIRecommendationService(
    llm_client=OpenAIClient(),
)


source = st.radio(
    "Job source",
    [
        "My jobs",
        "Global jobs",
    ],
    horizontal=True,
)

categories = st.multiselect(
    "Categories",
    options=category_service.categories(),
)

limit = st.selectbox(
    "Maximum jobs to check",
    [
        25,
        50,
        100,
        200,
    ],
    index=1,
)


if st.button(
    "Find jobs",
    type="primary",
):
    if not categories:
        st.warning(
            "Select at least one category."
        )

    else:
        if source == "My jobs":
            jobs = repository.list_user_jobs(
                user_id=current_user.id,
                categories=categories,
                limit=limit,
            )

        else:
            jobs = repository.list_global_jobs(
                categories=categories,
                limit=limit,
            )

        st.session_state[
            "jobs_to_analyze"
        ] = [
            dict(job)
            for job in jobs
        ]


jobs_to_analyze = st.session_state.get(
    "jobs_to_analyze",
    [],
)


if jobs_to_analyze:
    st.divider()

    st.subheader(
        f"{len(jobs_to_analyze)} jobs found"
    )

    for job in jobs_to_analyze:
        with st.expander(
            f"{job['title']} — "
            f"{job['company'] or 'Unknown company'}"
        ):
            st.write(
                f"Category: {job['category']}"
            )

            if job["sub_category"]:
                st.write(
                    f"Sub-category: "
                    f"{job['sub_category']}"
                )

            if job["location"]:
                st.write(
                    f"Location: {job['location']}"
                )

            if job["url"]:
                st.link_button(
                    "Open job",
                    job["url"],
                )

    st.divider()

    if st.button(
            "Analyze these jobs",
            type="primary",
            use_container_width=True,
    ):
        if not current_user.candidate_id:
            st.error(
                "Your account does not have "
                "a professional profile."
            )
            st.stop()

        candidate_id = current_user.candidate_id

        links_created = 0

        for job in jobs_to_analyze:
            created = ensure_candidate_job_analysis(
                candidate_id=candidate_id,
                job_id=job["id"],
            )

            if created:
                links_created += 1

        with st.spinner(
                "Analyzing jobs against your profile..."
        ):
            result = analysis_service.analyze_pending(
                candidate_id=candidate_id,
                limit=len(jobs_to_analyze),
            )

        st.success(
            f"Analysis complete. "
            f"{result['analyzed']} jobs analyzed."
        )

        st.write(
            f"New jobs added to your queue: "
            f"{links_created}"
        )

        st.write(
            f"Ready for review: "
            f"{result['ai_approved']}"
        )

        st.write(
            f"Automatically rejected: "
            f"{result['hard_rejected'] + result['matcher_rejected'] + result['ai_rejected']}"
        )

        if result["failed"]:
            st.warning(
                f"{result['failed']} jobs could not "
                f"be analyzed."
            )

        if result["errors"]:
            with st.expander(
                    "Analysis errors"
            ):
                for error in result["errors"]:
                    st.write(
                        f"{error['title']}: "
                        f"{error['error']}"
                    )
