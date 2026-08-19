import json

from models.career_development_recommendation import (
    CareerDevelopmentPriority,
    CareerDevelopmentRecommendation,
)


VALID_PRIORITIES = {
    "high",
    "medium",
    "low",
}

VALID_CONFIDENCE = {
    "low",
    "medium",
    "high",
}


def _string_list(
    value,
) -> list[str]:
    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def parse_career_development_response(
    response: str,
) -> CareerDevelopmentRecommendation:
    data = json.loads(response)

    priorities = []

    for item in data.get(
        "top_development_priorities",
        [],
    ):
        if not isinstance(item, dict):
            continue

        priority = str(
            item.get(
                "priority",
                "",
            )
        ).strip().lower()

        if priority not in VALID_PRIORITIES:
            priority = "medium"

        area = str(
            item.get(
                "area",
                "",
            )
        ).strip()

        why_it_matters = str(
            item.get(
                "why_it_matters",
                "",
            )
        ).strip()

        suggested_action = str(
            item.get(
                "suggested_action",
                "",
            )
        ).strip()

        if not (
            area
            and why_it_matters
            and suggested_action
        ):
            continue

        priorities.append(
            CareerDevelopmentPriority(
                area=area,
                why_it_matters=why_it_matters,

                evidence=_string_list(
                    item.get(
                        "evidence",
                        [],
                    )
                ),

                priority=priority,

                suggested_action=suggested_action,
            )
        )

    confidence = str(
        data.get(
            "data_confidence",
            "",
        )
    ).strip().lower()

    if confidence not in VALID_CONFIDENCE:
        confidence = "low"

    return CareerDevelopmentRecommendation(
        current_position=str(
            data.get(
                "current_position",
                "",
            )
        ).strip(),

        top_development_priorities=priorities,

        strengths_to_leverage=_string_list(
            data.get(
                "strengths_to_leverage",
                [],
            )
        ),

        market_patterns=_string_list(
            data.get(
                "market_patterns",
                [],
            )
        ),

        application_patterns=_string_list(
            data.get(
                "application_patterns",
                [],
            )
        ),

        next_best_moves=_string_list(
            data.get(
                "next_best_moves",
                [],
            )
        ),

        data_confidence=confidence,
    )
