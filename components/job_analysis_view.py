import html

import streamlit as st


RECOMMENDATION_LABELS = {
    "best_match": "Best Match",
    "strong_match": "Best Match",
    "potential": "Potential",
    "worth_second_look": "Potential",
    "good_opportunity": "Competitive",
    "competitive": "Competitive",
    "reject": "Reject",
    "rejected": "Reject",
    "system_rejected": "Reject",
    "not_analyzed": "Not analysed",
}


def _normalize_list_items(
    items,
) -> list[str]:
    if not items:
        return []

    if isinstance(items, str):
        raw_items = items.splitlines()
    elif isinstance(items, (list, tuple, set)):
        raw_items = items
    else:
        raw_items = [items]

    cleaned = []

    for item in raw_items:
        value = str(item or "").strip()

        while value.startswith(
            ("-", "*", "?")
        ):
            value = value[1:].strip()

        if value:
            cleaned.append(value)

    return cleaned


def _display_recommendation(
    recommendation: str,
) -> str:
    normalized = (
        str(recommendation or "")
        .strip()
        .lower()
        .replace(" ", "_")
    )

    return RECOMMENDATION_LABELS.get(
        normalized,
        normalized.replace("_", " ").title()
        if normalized
        else "Not analysed",
    )


def _render_analysis_card(
    title: str,
    text: str,
) -> None:
    safe_title = html.escape(title)
    safe_text = html.escape(text or "")

    st.html(
        f"""
        <div class="wp-analysis-card">
            <div class="wp-analysis-card-title">
                {safe_title}
            </div>
            <div class="wp-analysis-card-copy">
                {safe_text}
            </div>
        </div>
        """
    )


def _render_list_card(
    title: str,
    items,
    empty_message: str = "Nothing significant identified.",
) -> None:
    clean_items = _normalize_list_items(
        items
    )

    safe_title = html.escape(title)

    if clean_items:
        list_html = "".join(
            (
                '<div class="wp-analysis-list-item">'
                '<span class="wp-analysis-dot"></span>'
                f"<span>{html.escape(item)}</span>"
                "</div>"
            )
            for item in clean_items
        )
    else:
        list_html = (
            '<div class="wp-analysis-empty">'
            f"{html.escape(empty_message)}"
            "</div>"
        )

    st.html(
        f"""
        <div class="wp-analysis-detail-card">
            <div class="wp-analysis-detail-title">
                {safe_title}
            </div>
            {list_html}
        </div>
        """
    )


def render_job_analysis(
    item: dict,
    *,
    status_label: str | None = None,
) -> None:
    """
    Render the shared WorkPilot job analysis view.

    Actions such as Apply, Reject, Interview, Offer,
    notes and Open Job belong to the page using this
    component and remain outside this function.
    """

    analysis = item.get(
        "analysis",
        {},
    ) or {}

    location = (
        item.get("location")
        or "Location unavailable"
    )

    current_fit = item.get(
        "current_fit",
        "-",
    )

    growth_value = item.get(
        "growth_value",
        "-",
    )

    recommendation = (
        item.get("recommendation")
        or "not_analyzed"
    )

    recommendation_label = (
        _display_recommendation(
            recommendation
        )
    )

    requirements_met = analysis.get(
        "requirements_met",
        [],
    ) or []

    development_gaps = analysis.get(
        "development_gaps",
        [],
    ) or []

    structural_gaps = analysis.get(
        "structural_gaps",
        [],
    ) or []

    all_gaps = [
        *development_gaps,
        *structural_gaps,
    ]

    positive_points = analysis.get(
        "positive_points",
        [],
    ) or []

    priority_matches = analysis.get(
        "priority_matches",
        [],
    ) or []

    priority_conflicts = analysis.get(
        "priority_conflicts",
        [],
    ) or []

    personal_negatives = analysis.get(
        "personal_negatives",
        [],
    ) or []

    personal_tradeoffs = [
        *priority_conflicts,
        *personal_negatives,
    ]

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

    st.markdown(
        """
        <style>
        .wp-analysis-meta {
            color: #6B7D82;
            font-size: 0.86rem;
            margin-bottom: 0.9rem;
        }

        .wp-analysis-metrics {
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.75rem;
            margin-bottom: 1.15rem;
        }

        .wp-analysis-metric {
            background: #F8FAF9;
            border: 1px solid #E0E8E8;
            border-radius: 12px;
            padding: 0.9rem 1rem;
        }

        .wp-analysis-metric-label {
            color: #728388;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .wp-analysis-metric-value {
            color: #18363D;
            font-size: 1.35rem;
            font-weight: 750;
            line-height: 1.15;
        }

        .wp-analysis-pill {
            display: inline-block;
            background: #E2F1EE;
            color: #075665;
            border-radius: 99px;
            padding: 0.3rem 0.65rem;
            font-size: 0.8rem;
            font-weight: 800;
        }

        .wp-analysis-card {
            background: #FFFFFF;
            border: 1px solid #E0E8E8;
            border-radius: 12px;
            padding: 1rem 1.05rem;
            margin-bottom: 0.8rem;
        }

        .wp-analysis-card-title {
            color: #18363D;
            font-size: 0.9rem;
            font-weight: 750;
            margin-bottom: 0.45rem;
        }

        .wp-analysis-card-copy {
            color: #536A70;
            font-size: 0.9rem;
            line-height: 1.6;
            white-space: pre-line;
        }

        .wp-analysis-detail-card {
            background: #FFFFFF;
            border: 1px solid #E0E8E8;
            border-radius: 12px;
            padding: 1rem;
            min-height: 100%;
        }

        .wp-analysis-detail-title {
            color: #18363D;
            font-size: 0.88rem;
            font-weight: 750;
            margin-bottom: 0.7rem;
        }

        .wp-analysis-list-item {
            display: flex;
            align-items: flex-start;
            gap: 0.55rem;
            color: #536A70;
            font-size: 0.86rem;
            line-height: 1.5;
            margin-bottom: 0.45rem;
        }

        .wp-analysis-dot {
            width: 6px;
            height: 6px;
            min-width: 6px;
            border-radius: 50%;
            background: #075665;
            margin-top: 0.48rem;
        }

        .wp-analysis-empty {
            color: #89989C;
            font-size: 0.84rem;
        }

        .wp-analysis-details-title {
            color: #18363D;
            font-size: 1rem;
            font-weight: 750;
            margin: 0.35rem 0 0.85rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    safe_location = html.escape(
        str(location)
    )

    if status_label:
        safe_status = html.escape(
            str(status_label)
        )

        meta = (
            f"{safe_location}"
            f" &nbsp;·&nbsp; {safe_status}"
        )
    else:
        meta = safe_location

    st.html(
        f"""
        <div class="wp-analysis-meta">
            {meta}
        </div>

        <div class="wp-analysis-metrics">
            <div class="wp-analysis-metric">
                <div class="wp-analysis-metric-label">
                    CURRENT FIT
                </div>
                <div class="wp-analysis-metric-value">
                    {html.escape(str(current_fit))}
                </div>
            </div>

            <div class="wp-analysis-metric">
                <div class="wp-analysis-metric-label">
                    GROWTH VALUE
                </div>
                <div class="wp-analysis-metric-value">
                    {html.escape(str(growth_value))}
                </div>
            </div>

            <div class="wp-analysis-metric">
                <div class="wp-analysis-metric-label">
                    OPPORTUNITY TYPE
                </div>
                <div class="wp-analysis-metric-value">
                    <span class="wp-analysis-pill">
                        {html.escape(recommendation_label)}
                    </span>
                </div>
            </div>
        </div>
        """
    )

    _render_analysis_card(
        "Quick overview",
        simple_summary
        or (
            "A simple overview is not available "
            "for this analysis yet."
        ),
    )

    _render_analysis_card(
        "WorkPilot recommendation",
        simple_recommendation
        or final_recommendation
        or "No recommendation available.",
    )

    with st.expander(
        "View full analysis",
        expanded=False,
    ):
        st.html(
            """
            <div class="wp-analysis-details-title">
                Evidence and gaps
            </div>
            """
        )

        first_row = st.columns(
            2,
            gap="medium",
        )

        with first_row[0]:
            _render_list_card(
                "What you already bring",
                requirements_met,
            )

        with first_row[1]:
            _render_list_card(
                "Main gaps",
                all_gaps,
            )

        second_row = st.columns(
            2,
            gap="medium",
        )

        with second_row[0]:
            _render_list_card(
                "Positive signals",
                positive_points,
            )

        with second_row[1]:
            _render_list_card(
                "Trade-offs",
                personal_tradeoffs,
            )

        if priority_matches:
            _render_list_card(
                "Matches your priorities",
                priority_matches,
            )

        if reason:
            _render_analysis_card(
                "Why this role may be worth considering",
                reason,
            )

        if final_recommendation:
            _render_analysis_card(
                "Full recommendation",
                final_recommendation,
            )
