class ReportBuilder:
    RECOMMENDATION_ORDER = [
        "apply",
        "consider",
        "stretch",
    ]

    def build(self, recommendations: list[dict]) -> str:
        sections = [
            "# Today's Opportunities",
            "",
            f"Generated from {len(recommendations)} AI-reviewed jobs.",
        ]

        grouped_recommendations = self._group_by_recommendation(
            recommendations
        )

        for recommendation_name in self.RECOMMENDATION_ORDER:
            grouped_jobs = grouped_recommendations.get(
                recommendation_name,
                [],
            )

            if not grouped_jobs:
                continue

            sections.extend(
                [
                    "",
                    f"## {recommendation_name.title()}",
                ]
            )

            for recommendation in grouped_jobs:
                sections.extend(
                    self._build_job_section(recommendation)
                )

        return "\n".join(sections).strip() + "\n"

    def _group_by_recommendation(
        self,
        recommendations: list[dict],
    ) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}

        for recommendation in recommendations:
            recommendation_name = recommendation["analysis"][
                "recommendation"
            ]

            grouped.setdefault(
                recommendation_name,
                [],
            ).append(recommendation)

        return grouped

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

        reason = analysis.get("reason")

        if reason:
            sections.extend(
                [
                    "",
                    "**Why this role**",
                    "",
                    reason,
                ]
            )

        strengths = analysis.get("strengths") or []

        if strengths:
            sections.extend(
                [
                    "",
                    "**Strengths**",
                    "",
                    *[
                        f"- {strength}"
                        for strength in strengths
                    ],
                ]
            )

        gaps = analysis.get("gaps") or []

        if gaps:
            sections.extend(
                [
                    "",
                    "**Gaps**",
                    "",
                    *[
                        f"- {gap}"
                        for gap in gaps
                    ],
                ]
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

    def test_build_report_groups_jobs_by_recommendation():
        recommendations = [
            {
                "job": {
                    "title": "Support Engineer",
                    "company": "Company A",
                    "location": "Limerick",
                    "url": "https://example.com/job-a",
                },
                "analysis": {
                    "recommendation": "apply",
                    "current_fit": 85,
                    "growth_value": 80,
                    "reason": "Strong current fit.",
                    "strengths": ["technical support"],
                    "gaps": ["cloud"],
                },
            },
            {
                "job": {
                    "title": "Cloud Engineer",
                    "company": "Company B",
                    "location": "Dublin",
                    "url": "https://example.com/job-b",
                },
                "analysis": {
                    "recommendation": "stretch",
                    "current_fit": 60,
                    "growth_value": 95,
                    "reason": "High growth opportunity.",
                    "strengths": ["troubleshooting"],
                    "gaps": ["cloud infrastructure"],
                },
            },
        ]

        report = ReportBuilder().build(recommendations)

        assert "## Apply" in report
        assert "## Stretch" in report
        assert "## Consider" not in report

        assert report.index("## Apply") < report.index("## Stretch")
        assert "### Support Engineer — Company A" in report
        assert "### Cloud Engineer — Company B" in report
