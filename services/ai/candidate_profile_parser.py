import json


REQUIRED_FIELDS = {
    "current_role",
    "current_level",
    "professional_summary",
    "target_roles",
    "skills",
    "strengths",
    "development_areas",
    "professional_experiences",
    "proven_capabilities",
    "transferable_capabilities",
    "developing_capabilities",
    "technical_tools",
    "domain_experience",
    "competitive_role_families",
    "bridge_role_families",
    "target_role_families",
}


EXPERIENCE_REQUIRED_FIELDS = {
    "source_experience_id",
    "company",
    "stated_role",
    "inferred_role",
    "role_family",
    "summary",
    "responsibilities",
    "demonstrated_capabilities",
    "transferable_capabilities",
    "tools",
    "domains",
    "evidence",
}


def _validate_string_list(
    value,
    field_name: str,
) -> None:
    if not isinstance(value, list):
        raise ValueError(
            f"{field_name} must be a list."
        )

    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"{field_name} must contain only strings."
            )


def parse_candidate_profile_response(
    response: str,
) -> dict:
    data = json.loads(response)

    if not isinstance(data, dict):
        raise ValueError(
            "Candidate profile response must be a JSON object."
        )

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

    list_fields = [
        "target_roles",
        "skills",
        "strengths",
        "development_areas",
        "proven_capabilities",
        "transferable_capabilities",
        "developing_capabilities",
        "technical_tools",
        "domain_experience",
        "competitive_role_families",
        "bridge_role_families",
        "target_role_families",
    ]

    for field_name in list_fields:
        _validate_string_list(
            data[field_name],
            field_name,
        )

    experiences = data[
        "professional_experiences"
    ]

    if not isinstance(
        experiences,
        list,
    ):
        raise ValueError(
            "professional_experiences must be a list."
        )

    for index, experience in enumerate(
        experiences
    ):
        if not isinstance(
            experience,
            dict,
        ):
            raise ValueError(
                "Each professional_experience "
                "must be an object."
            )

        missing_experience_fields = (
            EXPERIENCE_REQUIRED_FIELDS
            - experience.keys()
        )

        if missing_experience_fields:
            raise ValueError(
                "Missing fields in "
                f"professional_experiences[{index}]: "
                + ", ".join(
                    sorted(
                        missing_experience_fields
                    )
                )
            )

        experience_text_fields = [
            "source_experience_id",
            "company",
            "stated_role",
            "inferred_role",
            "role_family",
            "summary",
        ]

        for field_name in (
            experience_text_fields
        ):
            if not isinstance(
                experience[field_name],
                str,
            ):
                raise ValueError(
                    "professional_experiences"
                    f"[{index}].{field_name} "
                    "must be a string."
                )

        experience_list_fields = [
            "responsibilities",
            "demonstrated_capabilities",
            "transferable_capabilities",
            "tools",
            "domains",
            "evidence",
        ]

        for field_name in (
            experience_list_fields
        ):
            _validate_string_list(
                experience[field_name],
                (
                    "professional_experiences"
                    f"[{index}].{field_name}"
                ),
            )

    return data
