import json


REQUIRED_FIELDS = {
    "current_role",
    "current_level",
    "professional_summary",
    "target_roles",
    "skills",
    "strengths",
    "development_areas",
}


def parse_candidate_profile_response(
    response: str,
) -> dict:
    data = json.loads(response)

    missing_fields = (
        REQUIRED_FIELDS - data.keys()
    )

    if missing_fields:
        raise ValueError(
            "Missing fields in candidate profile response: "
            + ", ".join(
                sorted(missing_fields)
            )
        )

    list_fields = [
        "target_roles",
        "skills",
        "strengths",
        "development_areas",
    ]

    for field_name in list_fields:
        if not isinstance(
            data[field_name],
            list,
        ):
            raise ValueError(
                f"{field_name} must be a list."
            )

    text_fields = [
        "current_role",
        "current_level",
        "professional_summary",
    ]

    for field_name in text_fields:
        if not isinstance(
            data[field_name],
            str,
        ):
            raise ValueError(
                f"{field_name} must be a string."
            )

    return data
