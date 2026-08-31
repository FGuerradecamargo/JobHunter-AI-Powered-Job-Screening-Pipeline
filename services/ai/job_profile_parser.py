import json
from typing import Any

from models.job_profile import JobProfile


VALID_SENIORITY = {
    "entry",
    "junior",
    "mid",
    "senior",
    "lead",
    "manager",
    "director",
    "executive",
    "unclear",
}

VALID_AUTONOMY = {
    "low",
    "medium",
    "high",
    "unclear",
}


def _string_list(
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


def parse_job_profile(
    response: str,
    job_id: str,
) -> JobProfile:
    data = json.loads(response)

    seniority = data.get(
        "seniority",
        "unclear",
    )

    if seniority not in VALID_SENIORITY:
        raise ValueError(
            f"Invalid seniority: {seniority}"
        )

    autonomy = data.get(
        "expected_autonomy",
        "unclear",
    )

    if autonomy not in VALID_AUTONOMY:
        raise ValueError(
            f"Invalid expected_autonomy: {autonomy}"
        )

    return JobProfile(
        job_id=job_id,
        canonical_role=str(
            data.get("canonical_role", "")
        ),
        role_family=str(
            data.get("role_family", "")
        ),
        seniority=seniority,
        core_mission=str(
            data.get("core_mission", "")
        ),
        must_have_capabilities=_string_list(
            data.get("must_have_capabilities"),
            "must_have_capabilities",
        ),
        must_have_experience=_string_list(
            data.get("must_have_experience"),
            "must_have_experience",
        ),
        nice_to_have=_string_list(
            data.get("nice_to_have"),
            "nice_to_have",
        ),
        key_responsibilities=_string_list(
            data.get("key_responsibilities"),
            "key_responsibilities",
        ),
        tools_and_technologies=_string_list(
            data.get("tools_and_technologies"),
            "tools_and_technologies",
        ),
        required_qualifications=_string_list(
            data.get("required_qualifications"),
            "required_qualifications",
        ),
        stakeholders_and_collaboration=_string_list(
            data.get(
                "stakeholders_and_collaboration"
            ),
            "stakeholders_and_collaboration",
        ),
        domain=str(
            data.get("domain", "")
        ),
        expected_autonomy=autonomy,
        structural_requirements=_string_list(
            data.get("structural_requirements"),
            "structural_requirements",
        ),
        work_conditions=_string_list(
            data.get("work_conditions"),
            "work_conditions",
        ),
        important_details=_string_list(
            data.get("important_details"),
            "important_details",
        ),
        role_context=str(
            data.get("role_context", "")
        ),
        summary=str(
            data.get("summary", "")
        ),
    )
