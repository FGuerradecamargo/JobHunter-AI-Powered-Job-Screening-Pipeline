import json
from pathlib import Path
from typing import Any

import streamlit as st


AI_RECOMMENDATIONS_FILE = Path("jobs_ai_recommended.json")

VISIBLE_RECOMMENDATIONS = {
    "recommended_apply",
    "worth_second_look",
}


def load_recommendations() -> list[dict[str, Any]]:
    if not AI_RECOMMENDATIONS_FILE.exists():
        return []

    try:
        content = AI_RECOMMENDATIONS_FILE.read_text(
            encoding="utf-8"
        )
        data = json.loads(content)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    return data


def get_visible_recommendations(
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []

    for item in recommendations:
        analysis = item.get("analysis", {})

        recommendation = analysis.get(
            "recommendation"
        )

        hard_conflicts = analysis.get(
            "hard_conflicts",
            [],
        )

        if (
            recommendation in VISIBLE_RECOMMENDATIONS
            and not hard_conflicts
        ):
            visible.append(item)

    return visible


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


def render_job(
    item: dict[str, Any],
) -> None:
    job = item.get("job", {})
    analysis = item.get("analysis", {})

    title = job.get(
        "title",
        "Untitled role",
    )

    company = job.get(
        "company",
        "Unknown company",
    )

    location = job.get(
        "location",
        "Location unavailable",
    )

    url = job.get("url")

    current_fit = analysis.get(
        "current_fit",
        "-",
    )

    growth_value = analysis.get(
        "growth_value",
        "-",
    )

    recommendation = analysis.get(
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
        metric_columns = st.columns(3)

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

        if url:
            st.link_button(
                "Open job",
                url,
            )


def main() -> None:
    st.set_page_config(
        page_title="JobHunter",
        page_icon="🎯",
        layout="wide",
    )

    st.title("JobHunter")

    st.caption(
        "Technical opportunities matched to your "
        "profile and preferences."
    )

    recommendations = load_recommendations()

    visible_jobs = get_visible_recommendations(
        recommendations
    )

    discarded_count = (
        len(recommendations)
        - len(visible_jobs)
    )

    summary_columns = st.columns(3)

    summary_columns[0].metric(
        "AI analyses",
        len(recommendations),
    )

    summary_columns[1].metric(
        "Worth reviewing",
        len(visible_jobs),
    )

    summary_columns[2].metric(
        "Discarded by decision layer",
        discarded_count,
    )

    st.divider()

    if not recommendations:
        st.warning(
            "No AI recommendations were found."
        )
        return

    if not visible_jobs:
        st.info(
            "No opportunities currently match your "
            "competitiveness and preferences."
        )
        return

    st.subheader(
        "Opportunities worth reviewing"
    )

    for item in visible_jobs:
        render_job(item)


if __name__ == "__main__":
    main()