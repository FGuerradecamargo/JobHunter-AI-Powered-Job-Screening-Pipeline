"""Normalize legacy CV shapes without treating stored content as executable markup."""
import json
import re


def _decode(value):
    if isinstance(value, str) and value.lstrip().startswith(("[", "{")):
        try:
            return json.loads(value)
        except (ValueError, RecursionError):
            return None
    return value


def _lines(value):
    value = _decode(value)
    if isinstance(value, str):
        values = value.splitlines()
    elif isinstance(value, list):
        values = value
    else:
        return []
    result = []
    for item in values:
        item = _decode(item)
        if isinstance(item, list):
            result.extend(_lines(item))
        elif isinstance(item, str):
            for line in item.splitlines():
                clean = re.sub(r"^(?:\s*[-*+\u2022]\s*)+", "", line).strip().strip("*_`").strip()
                if clean and any(c.isalnum() for c in clean):
                    result.append(clean)
    return result


def normalize_historical_cv(value):
    value = _decode(value)
    if not isinstance(value, dict):
        return None
    result = {
        "headline": "\n".join(_lines(value.get("headline"))),
        "professional_summary": "\n".join(_lines(value.get("professional_summary"))),
        "key_skills": _lines(value.get("key_skills")),
        "additional_relevant_information": _lines(value.get("additional_relevant_information")),
        "experiences": [],
    }
    experiences = _decode(value.get("experiences"))
    if isinstance(experiences, dict):
        experiences = [experiences]
    if isinstance(experiences, list):
        for experience in experiences:
            if not isinstance(experience, dict):
                continue
            item = {key: "\n".join(_lines(experience.get(key))) for key in ("role", "company", "period")}
            item["tailored_bullets"] = _lines(experience.get("tailored_bullets"))
            if any(item.values()):
                result["experiences"].append(item)
    return result if any(result.values()) else None
