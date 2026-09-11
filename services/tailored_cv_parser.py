import json

from models.tailored_cv_contract import (
    DraftTailoredCV,
    DraftTailoredCVExperience,
    TailoredCVStatement,
)


class TailoredCVParseError(ValueError):
    pass


def _required_string(data: dict, field: str, location: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise TailoredCVParseError(f"{location}.{field} must be a string.")
    return value


def _statement(value, location: str) -> TailoredCVStatement:
    if not isinstance(value, dict):
        raise TailoredCVParseError(f"{location} must be an object.")
    refs = value.get("evidence_refs")
    if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
        raise TailoredCVParseError(f"{location}.evidence_refs must be a string list.")
    return TailoredCVStatement(
        text=_required_string(value, "text", location),
        claim_type=_required_string(value, "claim_type", location),
        evidence_refs=refs,
    )


def _statement_list(data: dict, field: str) -> list[TailoredCVStatement]:
    values = data.get(field)
    if not isinstance(values, list):
        raise TailoredCVParseError(f"{field} must be a list.")
    return [_statement(item, f"{field}[{index}]") for index, item in enumerate(values)]


def parse_tailored_cv_response(response: dict | str) -> DraftTailoredCV:
    if isinstance(response, str):
        try:
            data = json.loads(response)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TailoredCVParseError("Generator response is not valid JSON.") from exc
    else:
        data = response
    if not isinstance(data, dict):
        raise TailoredCVParseError("Generator response must be a JSON object.")

    experiences = data.get("experiences")
    if not isinstance(experiences, list):
        raise TailoredCVParseError("experiences must be a list.")
    parsed_experiences = []
    for index, item in enumerate(experiences):
        location = f"experiences[{index}]"
        if not isinstance(item, dict):
            raise TailoredCVParseError(f"{location} must be an object.")
        bullets = item.get("bullets")
        if not isinstance(bullets, list):
            raise TailoredCVParseError(f"{location}.bullets must be a list.")
        parsed_experiences.append(
            DraftTailoredCVExperience(
                source_experience_id=_required_string(
                    item, "source_experience_id", location
                ),
                company=_required_string(item, "company", location),
                role=_required_string(item, "role", location),
                bullets=[
                    _statement(bullet, f"{location}.bullets[{bullet_index}]")
                    for bullet_index, bullet in enumerate(bullets)
                ],
            )
        )

    schema_version = _required_string(data, "schema_version", "draft")
    if schema_version != "tailored-cv-v1":
        raise TailoredCVParseError("draft.schema_version is not supported.")

    return DraftTailoredCV(
        candidate_id=_required_string(data, "candidate_id", "draft"),
        job_id=_required_string(data, "job_id", "draft"),
        application_context_signature=_required_string(
            data, "application_context_signature", "draft"
        ),
        headline=_statement(data.get("headline"), "headline"),
        professional_summary=_statement_list(data, "professional_summary"),
        key_skills=_statement_list(data, "key_skills"),
        experiences=parsed_experiences,
        additional_relevant_information=_statement_list(
            data, "additional_relevant_information"
        ),
        schema_version=schema_version,
    )
