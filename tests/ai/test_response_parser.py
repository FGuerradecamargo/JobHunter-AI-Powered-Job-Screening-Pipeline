from models.ai_recommendation import AIRecommendation
from services.ai.response_parser import parse_response


def test_parse_response_returns_ai_recommendation():
    raw_response = """
    {
      "recommendation": "apply",
      "current_fit": 80,
      "growth_value": 15,
      "strengths": [
        "technical support",
        "technical investigation"
      ],
      "gaps": [
        "limited cloud infrastructure experience"
      ],
      "reason": "Strong alignment with the candidate profile."
    }
    """

    result = parse_response(
        response=raw_response,
        job_id="test-001",
    )

    assert isinstance(result, AIRecommendation)
    assert result.job_id == "test-001"
    assert result.recommendation == "apply"
    assert result.current_fit == 80
    assert result.growth_value == 15
    assert "technical support" in result.strengths
    assert "limited cloud infrastructure experience" in result.gaps