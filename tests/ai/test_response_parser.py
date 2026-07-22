from services.ai.response_parser import parse_response


def test_parse_response_returns_ai_recommendation():
    raw_response = """
    {
      "recommendation": "recommended_apply",
      "competitive_status": "competitive_now",
      "current_fit": 80,
      "growth_value": 70,
      "job_level": "Intermediate technical support role",
      "candidate_level": "Experienced support and operations professional",
      "level_assessment": "The levels are compatible.",
      "core_requirements": [
        "technical troubleshooting",
        "incident investigation"
      ],
      "requirements_met": [
        "technical troubleshooting",
        "incident investigation"
      ],
      "strengths": [
        "technical support",
        "technical investigation"
      ],
      "development_gaps": [
        "cloud infrastructure"
      ],
      "structural_gaps": [],
      "positive_points": [
        "technical career progression"
      ],
      "personal_negatives": [
        "fully onsite work"
      ],
      "hard_conflicts": [],
      "reason": "The role matches the candidate's investigation background.",
      "final_reason": "The candidate can compete and the remaining gaps are learnable."
    }
    """

    result = parse_response(
        response=raw_response,
        job_id="test-001",
    )

    assert result.job_id == "test-001"
    assert result.recommendation == "recommended_apply"
    assert result.competitive_status == "competitive_now"
    assert result.current_fit == 80
    assert result.growth_value == 70

    assert (
        result.job_level
        == "Intermediate technical support role"
    )

    assert result.structural_gaps == []

    assert result.development_gaps == [
        "cloud infrastructure"
    ]