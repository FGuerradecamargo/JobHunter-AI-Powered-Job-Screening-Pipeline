import json
from typing import Any

from models.ai_recommendation import AIRecommendation
from models.tailored_cv import (
    TailoredCV,
    TailoredCVExperience,
)


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

VALID_DIRECTION_ALIGNMENTS = {
    "high",
    "medium",
    "low",
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


def parse_tailored_cv(
    value: Any,
) -> TailoredCV | None:
    if value is None:
        return None

    if not isinstance(value, dict):
        raise ValueError(
            "tailored_cv must be an object or null"
        )

    raw_experiences = value.get(
        "experiences",
        [],
    )

    if not isinstance(raw_experiences, list):
        raise ValueError(
            "tailored_cv.experiences must be a list"
        )

    experiences: list[
        TailoredCVExperience
    ] = []

    for item in raw_experiences:
        if not isinstance(item, dict):
            raise ValueError(
                "Each tailored CV experience "
                "must be an object"
            )

        experiences.append(
            TailoredCVExperience(
                source_experience_id=str(
                    item.get(
                        "source_experience_id",
                        "",
                    )
                ),
                company=str(
                    item.get("company", "")
                ),
                role=str(
                    item.get("role", "")
                ),
                tailored_bullets=(
                    validate_string_list(
                        item.get(
                            "tailored_bullets"
                        ),
                        (
                            "tailored_cv.experiences."
                            "tailored_bullets"
                        ),
                    )
                ),
            )
        )

    return TailoredCV(
        headline=str(
            value.get("headline", "")
        ),
        professional_summary=str(
            value.get(
                "professional_summary",
                "",
            )
        ),
        key_skills=validate_string_list(
            value.get("key_skills"),
            "tailored_cv.key_skills",
        ),
        experiences=experiences,
        additional_relevant_information=(
            validate_string_list(
                value.get(
                    "additional_relevant_information"
                ),
                (
                    "tailored_cv."
                    "additional_relevant_information"
                ),
            )
        ),
    )


def parse_response(
    response: str,
    job_id: str,
) -> AIRecommendation:
    data = json.loads(response)

    recommendation = data["recommendation"]
    competitive_status = data["competitive_status"]
    direction_alignment = data[
        "direction_alignment"
    ]

    if recommendation not in VALID_RECOMMENDATIONS:
        raise ValueError(
            f"Invalid recommendation: {recommendation}"
        )

    if competitive_status not in VALID_COMPETITIVE_STATUSES:
        raise ValueError(
            "Invalid competitive_status: "
            f"{competitive_status}"
        )

    if direction_alignment not in VALID_DIRECTION_ALIGNMENTS:
        raise ValueError(
            "Invalid direction_alignment: "
            f"{direction_alignment}"
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
        direction_alignment=direction_alignment,

        job_level=data.get("job_level", ""),
        candidate_level=data.get(
            "candidate_level",
            "",
        ),
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

        priority_matches=validate_string_list(
            data.get("priority_matches"),
            "priority_matches",
        ),
        priority_conflicts=validate_string_list(
            data.get("priority_conflicts"),
            "priority_conflicts",
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

        tailored_cv=parse_tailored_cv(
            data.get("tailored_cv")
        ),
    )
