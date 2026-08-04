import json
from typing import Any

from models.ai_recommendation import AIRecommendation


VALID_RECOMMENDATIONS = {
    "recommended_apply",
    "worth_second_look",
    "interview_practice_only",
    "not_competitive_now",
    "personally_unsuitable",
}

VALID_COMPETITIVE_STATUSES = {
    "competitive_now",
    "bridge_opportunity",
    "interview_practice_only",
    "not_competitive_now",
}


def validate_score(
    value: Any,
    field_name: str,
) -> int:
    if not isinstance(value, int):
        raise ValueError(
            f"{field_name} must be an integer"
        )

    if not 0 <= value <= 100:
        raise ValueError(
            f"{field_name} must be between 0 and 100"
        )

    return value


def validate_string_list(
    value: Any,
    field_name: str,
) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ValueError(
            f"{field_name} must be a list"
        )

    if not all(
        isinstance(item, str)
        for item in value
    ):
        raise ValueError(
            f"{field_name} must contain only strings"
        )

    return value


def parse_response(
    response: str,
    job_id: str,
) -> AIRecommendation:
    data = json.loads(response)

    recommendation = data["recommendation"]
    competitive_status = data["competitive_status"]

    if recommendation not in VALID_RECOMMENDATIONS:
        raise ValueError(
            f"Invalid recommendation: {recommendation}"
        )

    if competitive_status not in VALID_COMPETITIVE_STATUSES:
        raise ValueError(
            "Invalid competitive_status: "
            f"{competitive_status}"
        )

    current_fit = validate_score(
        data["current_fit"],
        "current_fit",
    )

    growth_value = validate_score(
        data["growth_value"],
        "growth_value",
    )

    return AIRecommendation(
        job_id=job_id,
        recommendation=recommendation,
        competitive_status=competitive_status,
        current_fit=current_fit,
        growth_value=growth_value,
        job_level=data.get("job_level", ""),
        candidate_level=data.get("candidate_level", ""),
        level_assessment=data.get(
            "level_assessment",
            "",
        ),
        core_requirements=validate_string_list(
            data.get("core_requirements"),
            "core_requirements",
        ),
        requirements_met=validate_string_list(
            data.get("requirements_met"),
            "requirements_met",
        ),
        strengths=validate_string_list(
            data.get("strengths"),
            "strengths",
        ),
        development_gaps=validate_string_list(
            data.get("development_gaps"),
            "development_gaps",
        ),
        structural_gaps=validate_string_list(
            data.get("structural_gaps"),
            "structural_gaps",
        ),
        positive_points=validate_string_list(
            data.get("positive_points"),
            "positive_points",
        ),
        personal_negatives=validate_string_list(
            data.get("personal_negatives"),
            "personal_negatives",
        ),
        hard_conflicts=validate_string_list(
            data.get("hard_conflicts"),
            "hard_conflicts",
        ),
        reason=data.get("reason", ""),
        final_reason=data.get(
            "final_reason",
            "",
        ),

        simple_summary=data.get(
            "simple_summary",
            "",
        ),
        simple_recommendation=data.get(
            "simple_recommendation",
            "",
        ),
    )
