from __future__ import annotations

from dataclasses import dataclass, field
from typing import MutableMapping

from models.interview_context import InterviewDetails
from models.interview_feedback import InterviewFeedback
from services.interview_context_service import InterviewContextService
from services.interview_details_repository import InterviewDetailsRepository
from services.interview_feedback_repository import InterviewFeedbackRepository
from services.interview_feedback_service import InterviewFeedbackService
from services.interview_preparation_service import InterviewPreparationService


INTERVIEW_DETAILS_STATE_PREFIX = "interview_details"
INTERVIEW_FEEDBACK_STATE_PREFIX = "interview_feedback"
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
    recruiter_feedback: list[str] = field(default_factory=list)
    candidate_self_reports: list[str] = field(default_factory=list)
    previously_discussed_topics: list[str] = field(default_factory=list)
    review_topics: list[str] = field(default_factory=list)
    next_stage_instructions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InterviewPreparationUIResult:
    visible: bool
    view: InterviewPreparationView | None = None
    details: InterviewDetails | None = None
    feedback: InterviewFeedback | None = None
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


def interview_feedback_state_key(candidate_id: str, job_id: str) -> str:
    return ":".join(
        (
            INTERVIEW_FEEDBACK_STATE_PREFIX,
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


class _NoFeedbackRepository:
    def get(self, _candidate_id: str, _job_id: str):
        return None


def load_interview_preparation_view(
    *,
    candidate_id: str,
    job_id: str,
    lifecycle_status: str,
    context_service=None,
    preparation_service=None,
    details_repository=None,
    feedback_repository=None,
) -> InterviewPreparationUIResult:
    if lifecycle_status not in {"applied", "in_process"}:
        return InterviewPreparationUIResult(visible=False)

    dependencies_injected = any(
        value is not None
        for value in (context_service, preparation_service, details_repository)
    )
    context_service = context_service or InterviewContextService()
    preparation_service = preparation_service or InterviewPreparationService(
        context_service=context_service
    )
    details_repository = details_repository or InterviewDetailsRepository()
    if feedback_repository is None:
        feedback_repository = (
            _NoFeedbackRepository()
            if dependencies_injected
            else InterviewFeedbackRepository()
        )
    try:
        context = context_service.build(candidate_id, job_id)
        preparation = preparation_service.build(candidate_id, job_id)
        details = details_repository.get(candidate_id, job_id)
        feedback = feedback_repository.get(candidate_id, job_id)
        if (
            context.candidate_id != candidate_id
            or preparation.candidate_id != candidate_id
            or (details is not None and details.candidate_id != candidate_id)
            or (feedback is not None and feedback.candidate_id != candidate_id)
        ):
            raise PermissionError("Candidate scope mismatch.")
        if (
            context.job_id != job_id
            or preparation.job_id != job_id
            or (details is not None and details.job_id != job_id)
            or (feedback is not None and feedback.job_id != job_id)
        ):
            raise PermissionError("Job scope mismatch.")
        if (
            preparation.analysis_id != context.analysis_id
            or preparation.interview_context_signature != context.source_signature
            or preparation.interview_stage != context.interview_stage
        ):
            raise PermissionError("Interview preparation source mismatch.")
        if feedback is not None and feedback.interview_stage not in {
            "interview", "final_interview"
        }:
            raise PermissionError("Interview feedback stage mismatch.")
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
        recruiter_feedback=[
            item.text
            for item in preparation.explicit_feedback
            if item.source_type == "recruiter_feedback"
        ],
        candidate_self_reports=[
            item.text
            for item in preparation.explicit_feedback
            if item.source_type == "candidate_self_report"
        ],
        previously_discussed_topics=list(
            preparation.previously_discussed_topics
        ),
        review_topics=list(preparation.review_topics),
        next_stage_instructions=list(preparation.next_stage_instructions),
    )
    return InterviewPreparationUIResult(
        visible=True,
        view=view,
        details=details or InterviewDetails(candidate_id=candidate_id, job_id=job_id),
        feedback=feedback or InterviewFeedback(
            candidate_id=candidate_id,
            job_id=job_id,
            interview_stage=context.interview_stage,
        ),
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
    feedback_repository=None,
) -> InterviewPreparationUIResult:
    feedback_repository = feedback_repository or _NoFeedbackRepository()
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
            feedback_repository=feedback_repository,
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
            feedback_repository=feedback_repository,
        )
        return InterviewPreparationUIResult(
            visible=result.visible,
            view=result.view,
            details=result.details,
            feedback=result.feedback,
            error_message=result.error_message,
            saved=result.visible,
        )
    except Exception:
        return InterviewPreparationUIResult(
            visible=False,
            error_message="Interview details could not be saved. Please try again.",
        )


def handle_interview_feedback_save(
    session_state: MutableMapping,
    *,
    candidate_id: str,
    job_id: str,
    lifecycle_status: str,
    save_requested: bool,
    recruiter_feedback: str,
    candidate_notes: str,
    discussed_topics: list[str],
    difficult_topics: list[str],
    next_stage_instructions: str,
    feedback_service,
    feedback_repository,
    context_service,
    preparation_service,
    details_repository,
) -> InterviewPreparationUIResult:
    if not save_requested:
        return load_interview_preparation_view(
            candidate_id=candidate_id,
            job_id=job_id,
            lifecycle_status=lifecycle_status,
            context_service=context_service,
            preparation_service=preparation_service,
            details_repository=details_repository,
            feedback_repository=feedback_repository,
        )
    try:
        saved = feedback_service.save(
            candidate_id,
            job_id,
            recruiter_feedback=recruiter_feedback,
            candidate_notes=candidate_notes,
            discussed_topics=discussed_topics,
            difficult_topics=difficult_topics,
            next_stage_instructions=next_stage_instructions,
        )
        if saved.candidate_id != candidate_id or saved.job_id != job_id:
            raise PermissionError("Saved feedback scope mismatch.")
        session_state[interview_feedback_state_key(candidate_id, job_id)] = saved
        result = load_interview_preparation_view(
            candidate_id=candidate_id,
            job_id=job_id,
            lifecycle_status=lifecycle_status,
            context_service=context_service,
            preparation_service=preparation_service,
            details_repository=details_repository,
            feedback_repository=feedback_repository,
        )
        return InterviewPreparationUIResult(
            visible=result.visible,
            view=result.view,
            details=result.details,
            feedback=result.feedback,
            error_message=result.error_message,
            saved=result.visible,
        )
    except Exception:
        return InterviewPreparationUIResult(
            visible=False,
            error_message="Interview feedback could not be saved. Please try again.",
        )
