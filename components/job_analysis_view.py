import streamlit as st


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


def _render_list(
    title: str,
    items,
) -> None:
    st.markdown(
        f"**{title}**"
    )

    clean_items = _normalize_list_items(
        items
    )

    if not clean_items:
        st.caption(
            "Nothing significant identified."
        )
        return

    for item in clean_items:
        st.markdown(
            f"- {item}"
        )


def _render_text_section(
    title: str,
    text: str,
    fallback: str,
) -> None:
    st.markdown(
        f"**{title}**"
    )

    if text:
        st.write(text)
    else:
        st.caption(fallback)


def render_job_analysis(
    item: dict,
    *,
    status_label: str | None = None,
) -> None:
    """
    Render the shared JobHunter job analysis view.

    Actions such as Apply, Reject, Interview, Offer,
    notes and Open Job belong to the page using this
    component and should remain outside this function.
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

    if status_label is None:
        metric_columns = st.columns(3)
    else:
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

    if status_label is not None:
        metric_columns[3].metric(
            "Status",
            status_label,
        )

    st.write(
        f"**Location:** {location}"
    )

    _render_text_section(
        "Quick overview",
        simple_summary,
        (
            "A simple overview is not available "
            "for this analysis yet."
        ),
    )

    _render_text_section(
        "My recommendation",
        simple_recommendation,
        (
            final_recommendation
            or "No recommendation available."
        ),
    )

    with st.expander(
        "View technical details",
        expanded=False,
    ):
        first_row = st.columns(2)

        with first_row[0]:
            _render_list(
                "What you already bring",
                requirements_met,
            )

        with first_row[1]:
            _render_list(
                "Main gaps",
                all_gaps,
            )

        st.divider()

        second_row = st.columns(2)

        with second_row[0]:
            _render_list(
                "Positive points",
                positive_points,
            )

        with second_row[1]:
            _render_list(
                "Personal tradeoffs",
                personal_tradeoffs,
            )

        if priority_matches:
            st.divider()

            _render_list(
                "Priority matches",
                priority_matches,
            )

        st.divider()

        _render_text_section(
            "Why this role may be worth considering",
            reason,
            "No explanation available.",
        )

        _render_text_section(
            "Full recommendation",
            final_recommendation,
            "No full recommendation available.",
        )
