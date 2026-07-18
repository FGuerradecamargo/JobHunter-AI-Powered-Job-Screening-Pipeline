import json

from models.ai_recommendation import AIRecommendation


VALID_RECOMMENDATIONS = {
    "apply",
    "consider",
    "stretch",
    "ignore",
}


def parse_response(
    response: str,
    job_id: str,
) -> AIRecommendation:
    data = json.loads(response)

    recommendation = data["recommendation"]
    current_fit = data["current_fit"]
    growth_value = data["growth_value"]

    if recommendation not in VALID_RECOMMENDATIONS:
        raise ValueError(
            f"Invalid recommendation: {recommendation}"
        )

    if not isinstance(current_fit, int):
        raise ValueError("current_fit must be an integer")

    if not 0 <= current_fit <= 100:
        raise ValueError("current_fit must be between 0 and 100")

    if not isinstance(growth_value, int):
        raise ValueError("growth_value must be an integer")

    if not 0 <= growth_value <= 100:
        raise ValueError("growth_value must be between 0 and 100")

    return AIRecommendation(
        job_id=job_id,
        recommendation=recommendation,
        current_fit=current_fit,
        growth_value=growth_value,
        strengths=data.get("strengths", []),
        gaps=data.get("gaps", []),
        reason=data.get("reason", ""),
    )