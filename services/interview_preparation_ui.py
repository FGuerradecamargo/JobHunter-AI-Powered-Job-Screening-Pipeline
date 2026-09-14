from __future__ import annotations

from dataclasses import dataclass, field
from typing import MutableMapping

from models.interview_context import InterviewDetails
from services.interview_context_service import InterviewContextService
from services.interview_details_repository import InterviewDetailsRepository
from services.interview_preparation_service import InterviewPreparationService


INTERVIEW_DETAILS_STATE_PREFIX = "interview_details"
PRIORITY_LABELS = {
    "explicit": "Specifically mentioned",
    "high": "High priority",
    "normal": "Prepare",
}


@dataclass(frozen=True)
class PreparationAreaView:
    topic: str
    priority_label: str
    source_label: str = ""
    what_to_demonstrate: str = ""
    example_direction: str = ""
    emphasis: str = ""
    caution: str = ""


@dataclass(frozen=True)
class InterviewPreparationView:
    title: str = "Interview Prep"
    role: str = ""
    company: str = ""
    stage: str = ""
    interview_type: str = ""
    interview_format: str = ""
    interviewer: str = ""
    duration: str = ""
    scheduled_at: str = ""
    summary_guidance: str = ""
    preparation_areas: list[PreparationAreaView] = field(default_factory=list)
    interview_instructions: list[str] = field(default_factory=list)
    rehearsal_prompts: list[str] = field(default_factory=list)
    questions_to_ask_the_company: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InterviewPreparationUIResult:
    visible: bool
    view: InterviewPreparationView | None = None
    details: InterviewDetails | None = None
    error_message: str = ""
    saved: bool = False


def interview_details_state_key(candidate_id: str, job_id: str) -> str:
    return ":".join(
        (
            INTERVIEW_DETAILS_STATE_PREFIX,
            str(candidate_id or "").strip(),
            str(job_id or "").strip(),
        )
    )


def _area_source_label(source_type: str) -> str:
    return {
        "explicit_interview_topic": "Specifically mentioned for this interview",
        "structural_gap": "Be precise here",
        "development_gap": "This is still developing",
    }.get(source_type, "")


def _safe_error() -> str:
    return "Interview preparation is not available right now. Please try again."


def load_interview_preparation_view(
    *,
    candidate_id: str,
    job_id: str,
    lifecycle_status: str,
    context_service=None,
    preparation_service=None,
    details_repository=None,
) -> InterviewPreparationUIResult:
    if lifecycle_status not in {"applied", "in_process"}:
        return InterviewPreparationUIResult(visible=False)

    context_service = context_service or InterviewContextService()
    preparation_service = preparation_service or InterviewPreparationService(
        context_service=context_service
    )
    details_repository = details_repository or InterviewDetailsRepository()
    try:
        context = context_service.build(candidate_id, job_id)
        preparation = preparation_service.build(candidate_id, job_id)
        details = details_repository.get(candidate_id, job_id)
        if (
            context.candidate_id != candidate_id
            or preparation.candidate_id != candidate_id
            or (details is not None and details.candidate_id != candidate_id)
        ):
            raise PermissionError("Candidate scope mismatch.")
        if (
            context.job_id != job_id
            or preparation.job_id != job_id
            or (details is not None and details.job_id != job_id)
        ):
            raise PermissionError("Job scope mismatch.")
    except ValueError:
        return InterviewPreparationUIResult(visible=False)
    except Exception:
        return InterviewPreparationUIResult(
            visible=False,
            error_message=_safe_error(),
        )

    stage = {
        "interview": "Interview",
        "final_interview": "Final interview",
    }.get(preparation.interview_stage, "")
    areas = [
        PreparationAreaView(
            topic=area.topic,
            priority_label=PRIORITY_LABELS.get(area.priority, "Prepare"),
            source_label=_area_source_label(area.source_type),
            what_to_demonstrate=area.what_to_demonstrate,
            example_direction=area.example_direction,
            emphasis=area.emphasis,
            caution=area.caution,
        )
        for area in preparation.preparation_areas
    ]
    view = InterviewPreparationView(
        role=context.job_title,
        company=context.company,
        stage=stage,
        interview_type=context.interview_type,
        interview_format=context.interview_format,
        interviewer=context.interviewer,
        duration=(
            f"{context.duration_minutes} minutes"
            if context.duration_minutes is not None
            else ""
        ),
        scheduled_at=context.scheduled_at,
        summary_guidance=preparation.summary_guidance,
        preparation_areas=areas,
        interview_instructions=list(preparation.interview_instructions),
        rehearsal_prompts=list(preparation.rehearsal_prompts),
        questions_to_ask_the_company=list(
            preparation.questions_to_ask_the_company
        ),
    )
    return InterviewPreparationUIResult(
        visible=True,
        view=view,
        details=details or InterviewDetails(candidate_id=candidate_id, job_id=job_id),
    )


def handle_interview_details_save(
    session_state: MutableMapping,
    *,
    candidate_id: str,
    job_id: str,
    lifecycle_status: str,
    save_requested: bool,
    details: InterviewDetails,
    details_repository,
    context_service,
    preparation_service,
) -> InterviewPreparationUIResult:
    if details.candidate_id != candidate_id or details.job_id != job_id:
        return InterviewPreparationUIResult(
            visible=False,
            error_message=_safe_error(),
        )
    if not save_requested:
        return load_interview_preparation_view(
            candidate_id=candidate_id,
            job_id=job_id,
            lifecycle_status=lifecycle_status,
            context_service=context_service,
            preparation_service=preparation_service,
            details_repository=details_repository,
        )
    try:
        saved = details_repository.save(details)
        if saved.candidate_id != candidate_id or saved.job_id != job_id:
            raise PermissionError("Saved details scope mismatch.")
        session_state[interview_details_state_key(candidate_id, job_id)] = saved
        result = load_interview_preparation_view(
            candidate_id=candidate_id,
            job_id=job_id,
            lifecycle_status=lifecycle_status,
            context_service=context_service,
            preparation_service=preparation_service,
            details_repository=details_repository,
        )
        return InterviewPreparationUIResult(
            visible=result.visible,
            view=result.view,
            details=result.details,
            error_message=result.error_message,
            saved=result.visible,
        )
    except Exception:
        return InterviewPreparationUIResult(
            visible=False,
            error_message="Interview details could not be saved. Please try again.",
        )
