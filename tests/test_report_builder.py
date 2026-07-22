from services.report_builder import ReportBuilder


def build_example_recommendation(
    recommendation: str = "recommended_apply",
) -> dict:
    return {
        "job": {
            "title": "Technical Support Engineer",
            "company": "Example Company",
            "location": "Dublin",
            "url": "https://example.com/job",
        },
        "analysis": {
            "recommendation": recommendation,
            "competitive_status": "competitive_now",
            "current_fit": 80,
            "growth_value": 90,
            "job_level": "Intermediate",
            "candidate_level": (
                "Experienced operations professional"
            ),
            "level_assessment": (
                "The candidate level is compatible."
            ),
            "reason": (
                "Strong fit for technical support "
                "and troubleshooting work."
            ),
            "core_requirements": [
                "technical troubleshooting",
            ],
            "requirements_met": [
                "technical troubleshooting",
            ],
            "strengths": [
                "root cause analysis",
            ],
            "development_gaps": [
                "cloud experience",
            ],
            "structural_gaps": [],
            "positive_points": [
                "career progression",
            ],
            "personal_negatives": [
                "fully onsite",
            ],
            "hard_conflicts": [],
            "final_reason": (
                "The candidate can compete for this role."
            ),
        },
    }


def test_build_report_contains_job_information():
    recommendations = [
        build_example_recommendation()
    ]

    report = ReportBuilder().build(
        recommendations
    )

    assert "# JobHunter Decision Report" in report
    assert "Generated from 1 AI-reviewed jobs." in report
    assert "Technical Support Engineer" in report
    assert "Example Company" in report
    assert "Dublin" in report
    assert "**Current fit:** 80" in report
    assert "**Growth value:** 90" in report
    assert "**Job level:** Intermediate" in report
    assert "**Level assessment**" in report
    assert "**Core requirements**" in report
    assert "**Development gaps**" in report
    assert "**Negative points for you**" in report
    assert "**Final recommendation**" in report
    assert "https://example.com/job" in report


def test_build_report_groups_jobs_by_recommendation():
    recommendations = [
        build_example_recommendation(
            "recommended_apply"
        ),
        build_example_recommendation(
            "not_competitive_now"
        ),
    ]

    report = ReportBuilder().build(
        recommendations
    )

    assert "## Recommended Applications" in report
    assert "## Not Competitive Now" in report

    assert (
        report.index("## Recommended Applications")
        <
        report.index("## Not Competitive Now")
    )


def test_build_report_omits_empty_fields():
    recommendation = build_example_recommendation()

    analysis = recommendation["analysis"]

    analysis["development_gaps"] = []
    analysis["structural_gaps"] = []
    analysis["personal_negatives"] = []
    analysis["hard_conflicts"] = []

    report = ReportBuilder().build(
        [recommendation]
    )

    assert "**Development gaps**" not in report
    assert "**Structural gaps**" not in report
    assert "**Negative points for you**" not in report
    assert "**Hard conflicts**" not in report