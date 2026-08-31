import json
from typing import Any

from models.ai_recommendation import AIRecommendation
from models.tailored_cv import (
    TailoredCV,
    TailoredCVExperience,
)
from models.interview_prep import InterviewPrep
from models.market_signal import MarketSignal


VALID_RECOMMENDATIONS = {
    "best_match",
    "potential",
    "good_opportunity",
    "reject",
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


def parse_market_signal(
    value: Any,
) -> MarketSignal:
    if value is None:
        return MarketSignal()

    if not isinstance(value, dict):
        raise ValueError(
            "market_signal must be an object"
        )

    return MarketSignal(
        role_family=str(
            value.get(
                "role_family",
                "",
            )
        ),
        best_match_blockers=validate_string_list(
            value.get(
                "best_match_blockers"
            ),
            "market_signal.best_match_blockers",
        ),
        market_strengths=validate_string_list(
            value.get(
                "market_strengths"
            ),
            "market_signal.market_strengths",
        ),
        what_would_raise_fit=validate_string_list(
            value.get(
                "what_would_raise_fit"
            ),
            "market_signal.what_would_raise_fit",
        ),
    )


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


def parse_interview_prep(
    value: Any,
) -> InterviewPrep | None:
    if value is None:
        return None

    if not isinstance(value, dict):
        raise ValueError(
            "interview_prep must be an object or null"
        )

    return InterviewPrep(
        what_the_company_needs=str(
            value.get(
                "what_the_company_needs",
                "",
            )
        ),
        what_you_should_demonstrate=(
            validate_string_list(
                value.get(
                    "what_you_should_demonstrate"
                ),
                (
                    "interview_prep."
                    "what_you_should_demonstrate"
                ),
            )
        ),
        strongest_evidence=validate_string_list(
            value.get("strongest_evidence"),
            "interview_prep.strongest_evidence",
        ),
        points_to_be_careful_with=(
            validate_string_list(
                value.get(
                    "points_to_be_careful_with"
                ),
                (
                    "interview_prep."
                    "points_to_be_careful_with"
                ),
            )
        ),
        likely_interview_topics=(
            validate_string_list(
                value.get(
                    "likely_interview_topics"
                ),
                (
                    "interview_prep."
                    "likely_interview_topics"
                ),
            )
        ),
        positioning=str(
            value.get(
                "positioning",
                "",
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

        market_signal=parse_market_signal(
            data.get("market_signal")
        ),

        tailored_cv=parse_tailored_cv(
            data.get("tailored_cv")
        ),

        interview_prep=parse_interview_prep(
            data.get("interview_prep")
        ),
    )


def parse_batch_response(
    response: str,
    requested_job_ids: list[str],
) -> list[AIRecommendation]:
    """
    Parse a batch response while guaranteeing that the
    returned jobs exactly match the requested jobs.

    Individual analyses are validated by parse_response(),
    so single-job and batch validation cannot drift.
    """
    normalized_requested_ids = [
        str(job_id)
        for job_id in requested_job_ids
    ]

    if not normalized_requested_ids:
        raise ValueError(
            "requested_job_ids cannot be empty"
        )

    if (
        len(normalized_requested_ids)
        != len(set(normalized_requested_ids))
    ):
        raise ValueError(
            "requested_job_ids contains duplicates"
        )

    data = json.loads(response)

    if not isinstance(data, dict):
        raise ValueError(
            "Batch response must be an object"
        )

    raw_results = data.get("results")

    if not isinstance(raw_results, list):
        raise ValueError(
            "Batch response results must be a list"
        )

    analyses_by_job_id: dict[
        str,
        AIRecommendation,
    ] = {}

    for item in raw_results:
        if not isinstance(item, dict):
            raise ValueError(
                "Each batch result must be an object"
            )

        raw_job_id = item.get("job_id")

        if raw_job_id is None:
            raise ValueError(
                "Batch result is missing job_id"
            )

        job_id = str(raw_job_id)

        if not job_id:
            raise ValueError(
                "Batch result contains empty job_id"
            )

        if job_id in analyses_by_job_id:
            raise ValueError(
                f"Duplicate batch job_id: {job_id}"
            )

        analysis = item.get("analysis")

        if not isinstance(analysis, dict):
            raise ValueError(
                f"Batch analysis for {job_id} "
                f"must be an object"
            )

        analyses_by_job_id[job_id] = (
            parse_response(
                response=json.dumps(
                    analysis,
                    ensure_ascii=False,
                ),
                job_id=job_id,
            )
        )

    requested_set = set(
        normalized_requested_ids
    )

    returned_set = set(
        analyses_by_job_id
    )

    missing = (
        requested_set
        - returned_set
    )

    unexpected = (
        returned_set
        - requested_set
    )

    if missing or unexpected:
        details = []

        if missing:
            details.append(
                "missing="
                + ", ".join(
                    sorted(missing)
                )
            )

        if unexpected:
            details.append(
                "unexpected="
                + ", ".join(
                    sorted(unexpected)
                )
            )

        raise ValueError(
            "Batch job ID mismatch: "
            + "; ".join(details)
        )

    return [
        analyses_by_job_id[job_id]
        for job_id in normalized_requested_ids
    ]




def _parse_memory_interpretation_items(
    value: Any,
    *,
    field_name: str,
    allowed_evidence_refs: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(
            f"{field_name} must be a list"
        )

    results: list[
        dict[str, Any]
    ] = []

    seen_statements: set[str] = set()

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(
                f"{field_name}[{index}] "
                "must be an object"
            )

        if set(item.keys()) != {
            "statement",
            "confidence",
            "evidence_refs",
        }:
            raise ValueError(
                f"{field_name}[{index}] "
                "has invalid fields"
            )

        statement = item[
            "statement"
        ]

        if not isinstance(
            statement,
            str,
        ):
            raise ValueError(
                f"{field_name}[{index}]."
                "statement must be a string"
            )

        statement = statement.strip()

        if not statement:
            raise ValueError(
                f"{field_name}[{index}]."
                "statement must be non-empty"
            )

        normalized_statement = (
            statement.casefold()
        )

        if (
            normalized_statement
            in seen_statements
        ):
            raise ValueError(
                f"{field_name} contains "
                "duplicate statements"
            )

        seen_statements.add(
            normalized_statement
        )

        confidence = item[
            "confidence"
        ]

        if not isinstance(
            confidence,
            int,
        ):
            raise ValueError(
                f"{field_name}[{index}]."
                "confidence must be an integer"
            )

        if not 0 <= confidence <= 100:
            raise ValueError(
                f"{field_name}[{index}]."
                "confidence must be between "
                "0 and 100"
            )

        evidence_refs = item[
            "evidence_refs"
        ]

        if not isinstance(
            evidence_refs,
            list,
        ):
            raise ValueError(
                f"{field_name}[{index}]."
                "evidence_refs must be a list"
            )

        if not all(
            isinstance(ref, str)
            for ref in evidence_refs
        ):
            raise ValueError(
                f"{field_name}[{index}]."
                "evidence_refs must contain "
                "only strings"
            )

        normalized_refs = []

        for ref in evidence_refs:
            normalized_ref = (
                ref.strip()
            )

            if (
                normalized_ref
                not in allowed_evidence_refs
            ):
                raise ValueError(
                    "Career Memory response "
                    "contains unknown "
                    "evidence_ref: "
                    f"{normalized_ref!r}"
                )

            if (
                normalized_ref
                not in normalized_refs
            ):
                normalized_refs.append(
                    normalized_ref
                )

        results.append(
            {
                "statement": statement,
                "confidence": confidence,
                "evidence_refs": (
                    normalized_refs
                ),
            }
        )

    return results


def parse_career_memory_response(
    *,
    response: str,
    allowed_evidence_refs: set[str],
) -> dict[str, Any]:
    data = json.loads(
        response
    )

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Career Memory response "
            "must be an object"
        )

    if set(data.keys()) != {
        "inferences",
        "hypotheses",
        "continuity_note",
    }:
        raise ValueError(
            "Career Memory response "
            "has invalid top-level fields"
        )

    continuity_note = data[
        "continuity_note"
    ]

    if not isinstance(
        continuity_note,
        str,
    ):
        raise ValueError(
            "continuity_note must "
            "be a string"
        )

    continuity_note = (
        continuity_note.strip()
    )

    if len(continuity_note) > 1000:
        raise ValueError(
            "continuity_note is too long"
        )

    return {
        "inferences": (
            _parse_memory_interpretation_items(
                data["inferences"],
                field_name="inferences",
                allowed_evidence_refs=(
                    allowed_evidence_refs
                ),
            )
        ),
        "hypotheses": (
            _parse_memory_interpretation_items(
                data["hypotheses"],
                field_name="hypotheses",
                allowed_evidence_refs=(
                    allowed_evidence_refs
                ),
            )
        ),
        "continuity_note": (
            continuity_note
        ),
    }
