import json


REQUIRED_FIELDS = {
    "competitive_role_families",
    "bridge_role_families",
    "target_role_families",
    "relevant_proven_capabilities",
    "relevant_transferable_capabilities",
    "relevant_developing_capabilities",
    "relevant_tools",
    "relevant_domains",
    "relevant_strengths",
    "relevant_experience_ids",
    "development_gaps",
    "development_priorities",
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


def parse_objective_profile_response(
    response: str,
) -> dict:
    data = json.loads(response)

    if not isinstance(data, dict):
        raise ValueError(
            "Objective profile response must be a JSON object."
        )

    missing_fields = (
        REQUIRED_FIELDS - data.keys()
    )

    if missing_fields:
        raise ValueError(
            "Missing fields in objective profile response: "
            + ", ".join(
                sorted(missing_fields)
            )
        )

    for field_name in REQUIRED_FIELDS:
        _validate_string_list(
            data[field_name],
            field_name,
        )

    return data
