class ReportBuilder:
    RECOMMENDATION_ORDER = [
        "recommended_apply",
        "worth_second_look",
        "interview_practice_only",
        "not_competitive_now",
        "personally_unsuitable",
    ]

    RECOMMENDATION_TITLES = {
        "recommended_apply": "Recommended Applications",
        "worth_second_look": "Worth a Second Look",
        "interview_practice_only": "Interview Practice Only",
        "not_competitive_now": "Not Competitive Now",
        "personally_unsuitable": "Personally Unsuitable",
    }

    def build(
        self,
        recommendations: list[dict],
    ) -> str:
        sections = [
            "# JobHunter Decision Report",
            "",
            (
                f"Generated from {len(recommendations)} "
                "AI-reviewed jobs."
            ),
            "",
            (
                "> This report provides decision-support "
                "recommendations. It does not guarantee "
                "candidate suitability, interview selection "
                "or hiring outcome. The final decision always "
                "belongs to the candidate."
            ),
        ]

        grouped = self._group_by_recommendation(
            recommendations
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
                    for value in values
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

        if current_fit is not None:
            sections.append(
                f"**Current fit:** {current_fit}"
            )

        growth_value = analysis.get("growth_value")

        if growth_value is not None:
            sections.append(
                f"**Growth value:** {growth_value}"
            )

        job_level = analysis.get("job_level")

        if job_level:
            sections.append(
                f"**Job level:** {job_level}"
            )

        candidate_level = analysis.get(
            "candidate_level"
        )

        if candidate_level:
            sections.append(
                f"**Candidate level:** {candidate_level}"
            )

        self._append_text_section(
            sections,
            "Level assessment",
            analysis.get("level_assessment"),
        )

        self._append_text_section(
            sections,
            "Why you might apply",
            analysis.get("reason"),
        )

        self._append_list_section(
            sections,
            "Core requirements",
            analysis.get("core_requirements"),
        )

        self._append_list_section(
            sections,
            "Core requirements you already meet",
            analysis.get("requirements_met"),
        )

        self._append_list_section(
            sections,
            "Strengths you bring",
            analysis.get("strengths"),
        )

        self._append_list_section(
            sections,
            "Development gaps",
            analysis.get("development_gaps"),
        )

        self._append_list_section(
            sections,
            "Structural gaps",
            analysis.get("structural_gaps"),
        )

        self._append_list_section(
            sections,
            "Positive points for you",
            analysis.get("positive_points"),
        )

        self._append_list_section(
            sections,
            "Negative points for you",
            analysis.get("personal_negatives"),
        )

        self._append_list_section(
            sections,
            "Hard conflicts",
            analysis.get("hard_conflicts"),
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