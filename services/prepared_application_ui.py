from dataclasses import dataclass, field
from typing import MutableMapping

from models.prepare_application import PrepareApplicationResult
from services.application_contract_builder import (
    APPLICATION_ELIGIBLE_RECOMMENDATIONS,
)


PREPARED_APPLICATION_STATE_PREFIX = "prepared_application"


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

    session_state[
        prepared_application_state_key(candidate_id, job_id)
    ] = result
    return result


def build_prepared_cv_view(result: PrepareApplicationResult) -> PreparedCVView | None:
    if result.status != "prepared" or result.cv is None:
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
    if result.status == "generation_failed":
        return "The generated material did not pass validation."
    if result.error_code == "preparation_unavailable":
        return "Application preparation is currently unavailable."
    return "We could not prepare this application."
