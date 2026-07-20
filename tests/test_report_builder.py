from services.report_builder import ReportBuilder


def test_build_report_contains_job_information():
    recommendations = [
        {
            "job": {
                "title": "Technical Support Engineer",
                "company": "Example Company",
                "location": "Dublin",
                "url": "https://example.com/job",
            },
            "analysis": {
                "recommendation": "apply",
                "current_fit": 80,
                "growth_value": 90,
                "reason": (
                    "Strong fit for technical support "
                    "and troubleshooting work."
                ),
                "strengths": [
                    "technical support",
                    "root cause analysis",
                ],
                "gaps": [
                    "cloud experience",
                ],
            },
        }
    ]

    report = ReportBuilder().build(recommendations)

    assert "# Today's Opportunities" in report
    assert "Generated from 1 AI-reviewed jobs." in report
    assert "Technical Support Engineer" in report
    assert "Example Company" in report
    assert "Dublin" in report
    assert "80" in report
    assert "90" in report
    assert "Strong fit for technical support" in report
    assert "- technical support" in report
    assert "- cloud experience" in report
    assert "https://example.com/job" in report


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


def test_build_report_omits_empty_fields():
        recommendations = [
            {
                "job": {
                    "title": "Support Engineer",
                    "company": "Example Company",
                    "location": None,
                    "url": None,
                },
                "analysis": {
                    "recommendation": "consider",
                    "current_fit": 70,
                    "growth_value": None,
                    "reason": None,
                    "strengths": [],
                    "gaps": [],
                },
            }
        ]

        report = ReportBuilder().build(recommendations)

        assert "### Support Engineer — Example Company" in report
        assert "**Current fit:** 70" in report

        assert "None" not in report
        assert "**Location:**" not in report
        assert "**Growth value:**" not in report
        assert "**Why this role**" not in report
        assert "**Strengths**" not in report
        assert "**Gaps**" not in report
        assert "**Job link:**" not in report