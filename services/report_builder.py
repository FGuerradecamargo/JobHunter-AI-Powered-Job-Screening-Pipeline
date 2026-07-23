class ReportBuilder:
    RECOMMENDATION_ORDER = [
        "recommended_apply",
        "worth_second_look",
    ]

    RECOMMENDATION_TITLES = {
        "recommended_apply": "Recommended Applications",
        "worth_second_look": "Worth a Second Look",
    }

    @staticmethod
    def _should_include(
        recommendation: dict,
    ) -> bool:
        analysis = recommendation["analysis"]

        recommendation_name = analysis.get(
            "recommendation"
        )

        hard_conflicts = analysis.get(
            "hard_conflicts"
        ) or []

        return (
            recommendation_name
            in {
                "recommended_apply",
                "worth_second_look",
            }
            and not hard_conflicts
        )

    def build(
        self,
        recommendations: list[dict],
    ) -> str:
        visible_recommendations = [
            recommendation
            for recommendation in recommendations
            if self._should_include(recommendation)
        ]

        sections = [
            "# JobHunter Decision Report",
            "",
            (
                f"{len(visible_recommendations)} opportunities "
                "matched your competitiveness and preferences."
            ),
            "",
            (
                "> This report shows only opportunities worth "
                "your time based on competitiveness and "
                "personal constraints."
            ),
        ]

        grouped = self._group_by_recommendation(
            visible_recommendations
        )

        for recommendation_name in self.RECOMMENDATION_ORDER:
            grouped_jobs = grouped.get(
                recommendation_name,
                [],
            )

            if not grouped_jobs:
                continue

            title = self.RECOMMENDATION_TITLES[
                recommendation_name
            ]

            sections.extend(
                [
                    "",
                    f"## {title}",
                ]
            )

            for recommendation in grouped_jobs:
                sections.extend(
                    self._build_job_section(
                        recommendation
                    )
                )

        return "\n".join(sections).strip() + "\n"

    def _group_by_recommendation(
        self,
        recommendations: list[dict],
    ) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}

        for recommendation in recommendations:
            recommendation_name = recommendation[
                "analysis"
            ]["recommendation"]

            grouped.setdefault(
                recommendation_name,
                [],
            ).append(recommendation)

        return grouped

    @staticmethod
    def _append_text_section(
        sections: list[str],
        title: str,
        value: str | None,
    ) -> None:
        if not value:
            return

        sections.extend(
            [
                "",
                f"**{title}**",
                "",
                value,
            ]
        )

    @staticmethod
    def _append_list_section(
        sections: list[str],
        title: str,
        values: list[str] | None,
        limit: int = 4,
    ) -> None:
        if not values:
            return

        sections.extend(
            [
                "",
                f"**{title}**",
                "",
                *[
                    f"- {value}"
                    for value in values[:limit]
                ],
            ]
        )

    def _build_job_section(
        self,
        recommendation: dict,
    ) -> list[str]:
        job = recommendation["job"]
        analysis = recommendation["analysis"]

        title = job.get("title") or "Untitled role"
        company = job.get("company") or "Unknown company"

        sections = [
            "",
            f"### {title} — {company}",
        ]

        location = job.get("location")

        if location:
            sections.extend(
                [
                    "",
                    f"**Location:** {location}",
                ]
            )

        competitive_status = analysis.get(
            "competitive_status"
        )

        if competitive_status:
            sections.append(
                "**Competitive status:** "
                f"{competitive_status}"
            )

        current_fit = analysis.get("current_fit")
        growth_value = analysis.get("growth_value")

        if current_fit is not None:
            sections.append(
                f"**Current fit:** {current_fit}"
            )

        if growth_value is not None:
            sections.append(
                f"**Growth value:** {growth_value}"
            )

        self._append_text_section(
            sections,
            "Why this role is worth considering",
            analysis.get("reason"),
        )

        strengths = (
            analysis.get("requirements_met", [])
            + analysis.get("strengths", [])
        )

        self._append_list_section(
            sections,
            "What you already bring",
            strengths,
            limit=4,
        )

        gaps = (
            analysis.get("development_gaps", [])
            + analysis.get("structural_gaps", [])
        )

        self._append_list_section(
            sections,
            "Main gaps",
            gaps,
            limit=4,
        )

        self._append_list_section(
            sections,
            "Positive points",
            analysis.get("positive_points"),
            limit=4,
        )

        self._append_list_section(
            sections,
            "Personal tradeoffs",
            analysis.get("personal_negatives"),
            limit=4,
        )

        self._append_text_section(
            sections,
            "Final recommendation",
            analysis.get("final_reason"),
        )

        url = job.get("url")

        if url:
            sections.extend(
                [
                    "",
                    f"**Job link:** {url}",
                ]
            )

        return sections