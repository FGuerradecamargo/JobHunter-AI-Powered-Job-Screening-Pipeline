from dataclasses import dataclass, field
from typing import MutableMapping

from models.prepare_application import PrepareApplicationResult
from services.tailored_cv_diagnostics import validation_failure_message
from services.application_contract_builder import (
    APPLICATION_ELIGIBLE_RECOMMENDATIONS,
)


PREPARED_APPLICATION_STATE_PREFIX = "prepared_application"


def _has_valid_prepared_scope(result: PrepareApplicationResult) -> bool:
    if result.status != "prepared":
        return True
    return bool(
        result.generation_status in {"validated", "validated_after_repair"}
        and result.cv is not None
        and result.cv.candidate_id == result.candidate_id
        and result.cv.job_id == result.job_id
        and result.application_context_signature
        and result.cv.application_context_signature
        == result.application_context_signature
    )


@dataclass(frozen=True)
class PreparedCVExperienceView:
    role: str
    company: str
    bullets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreparedCVView:
    headline: str
    professional_summary: list[str] = field(default_factory=list)
    key_skills: list[str] = field(default_factory=list)
    experiences: list[PreparedCVExperienceView] = field(default_factory=list)
    additional_information: list[str] = field(default_factory=list)
    status_text: str = "Validated against your WorkPilot evidence"


def prepared_application_state_key(candidate_id: str, job_id: str) -> str:
    return ":".join(
        (
            PREPARED_APPLICATION_STATE_PREFIX,
            str(candidate_id or "").strip(),
            str(job_id or "").strip(),
        )
    )


def is_prepare_application_eligible(analysis: dict) -> bool:
    if not isinstance(analysis, dict):
        return False
    recommendation = str(
        analysis.get("recommendation") or analysis.get("bucket") or ""
    ).strip()
    return recommendation in APPLICATION_ELIGIBLE_RECOMMENDATIONS


def get_prepared_application(
    session_state: MutableMapping,
    *,
    candidate_id: str,
    job_id: str,
) -> PrepareApplicationResult | None:
    value = session_state.get(
        prepared_application_state_key(candidate_id, job_id)
    )
    if not isinstance(value, PrepareApplicationResult):
        return None
    if value.candidate_id != candidate_id or value.job_id != job_id:
        return None
    if not _has_valid_prepared_scope(value):
        return None
    return value


def handle_prepare_application_action(
    session_state: MutableMapping,
    *,
    candidate_id: str,
    job_id: str,
    analysis: dict,
    action_requested: bool,
    preparation_service=None,
) -> PrepareApplicationResult | None:
    current = get_prepared_application(
        session_state,
        candidate_id=candidate_id,
        job_id=job_id,
    )
    if not action_requested:
        return current
    if current is not None and current.status == "prepared":
        return current
    if not is_prepare_application_eligible(analysis):
        return PrepareApplicationResult(
            status="ineligible",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code="ineligible_application",
        )
    if preparation_service is None:
        return PrepareApplicationResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code="preparation_unavailable",
        )

    result = preparation_service.prepare(candidate_id, job_id)
    if not isinstance(result, PrepareApplicationResult):
        return PrepareApplicationResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code="invalid_preparation_result",
        )
    if result.candidate_id != candidate_id or result.job_id != job_id:
        return PrepareApplicationResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code="scope_mismatch",
        )
    if not _has_valid_prepared_scope(result):
        return PrepareApplicationResult(
            status="failed",
            candidate_id=candidate_id,
            job_id=job_id,
            error_code="invalid_preparation_result",
        )

    session_state[
        prepared_application_state_key(candidate_id, job_id)
    ] = result
    return result


def build_prepared_cv_view(result: PrepareApplicationResult) -> PreparedCVView | None:
    if result.status != "prepared" or not _has_valid_prepared_scope(result):
        return None
    cv = result.cv
    return PreparedCVView(
        headline=cv.headline.text,
        professional_summary=[item.text for item in cv.professional_summary],
        key_skills=[item.text for item in cv.key_skills],
        experiences=[
            PreparedCVExperienceView(
                role=item.role,
                company=item.company,
                bullets=[bullet.text for bullet in item.bullets],
            )
            for item in cv.experiences
        ],
        additional_information=[
            item.text for item in cv.additional_relevant_information
        ],
    )


def prepared_application_error_message(
    result: PrepareApplicationResult,
) -> str:
    if result.status == "ineligible":
        return "This opportunity is not eligible for application preparation."
    if result.error_code == "analysis_not_found":
        return "The analyzed opportunity is no longer available."
    if result.error_code == "preparation_unavailable":
        return "Application preparation is currently unavailable."
    if result.error_code == "generation_in_progress":
        return "This tailored CV is already being generated. Please wait."
    if result.error_code == "generation_claim_failed":
        return "Application preparation is temporarily unavailable."
    if result.error_code in {"generator_client_error", "repair_client_error", "generation_service_error"}:
        return "Tailored CV generation could not be completed. Please try again later."
    if result.error_code == "no_selected_evidence":
        return "There is no selected evidence available to prepare this CV."
    if result.status == "generation_failed":
        return validation_failure_message(result)
    return "We could not prepare this application."
