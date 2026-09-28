from __future__ import annotations


def render_interview_rounds(
    st,
    *,
    candidate_id,
    job_id,
    repository=None,
    preparation_service=None,
    read_only=False,
    compact=False,
):
    """Round-scoped interview UI. Domain writes remain in existing repositories."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from models.application_tracking import InterviewRoundFeedback
    from services.interview_round_repository import InterviewRoundRepository
    from services.application_outcome_repository import ApplicationOutcomeRepository
    from services.interview_preparation_service import InterviewPreparationService

    repository = repository or InterviewRoundRepository()
    outcomes = ApplicationOutcomeRepository()

    relationship = outcomes.get_application(
        candidate_id,
        job_id,
    )

    if (
        relationship is None
        or relationship["status"]
        not in {
            "applied",
            "in_process",
            "offer",
            "rejected_before_interview",
            "rejected_after_interview",
        }
    ):
        return

    outcome = outcomes.get(candidate_id, job_id)

    active = (
        relationship["status"] in {"applied", "in_process"}
        and not (outcome and outcome.final_status)
        and not read_only
    )

    rounds = repository.list(candidate_id, job_id)

    if compact:
        if rounds:
            st.caption(
                f"{len(rounds)} interview round"
                + ("" if len(rounds) == 1 else "s")
                + " recorded."
            )
        else:
            st.caption(
                "No interview rounds recorded yet."
            )
    else:
        st.subheader("Interviews")

    def create_round_form():
        token_key = f"round_request:{candidate_id}:{job_id}"

        if token_key not in st.session_state:
            st.session_state[token_key] = uuid4().hex

        with st.form(
            f"new_round:{candidate_id}:{job_id}"
        ):
            scheduled = st.checkbox(
                "Date and time confirmed"
            )

            date_col, time_col = st.columns(2)

            with date_col:
                day = st.date_input(
                    "Interview date",
                    value=datetime.now(timezone.utc).date(),
                )

            with time_col:
                time = st.time_input(
                    "Interview time"
                )

            zone_col, type_col = st.columns(2)

            with zone_col:
                zone = st.text_input(
                    "Time zone",
                    value="Europe/Dublin",
                )

            with type_col:
                kind = st.text_input(
                    "Interview type",
                    placeholder="Recruiter, technical, panel...",
                )

            names_col, roles_col = st.columns(2)

            with names_col:
                names = st.text_area(
                    "Interviewer names (optional)",
                    height=86,
                )

            with roles_col:
                roles = st.text_area(
                    "Interviewer roles (optional)",
                    height=86,
                )

            notes = st.text_area(
                "Notes",
                height=92,
                placeholder="Anything useful for this round.",
            )

            create = st.form_submit_button(
                "Add interview round"
            )

        if create:
            try:
                scheduled_at = (
                    datetime.combine(
                        day,
                        time,
                        ZoneInfo(zone),
                    ).isoformat()
                    if scheduled
                    else ""
                )

                repository.create(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    scheduled_at=scheduled_at,
                    interviewer_names=names.splitlines(),
                    interviewer_roles=roles.splitlines(),
                    interview_type=kind,
                    notes=notes,
                    interview_id=st.session_state[token_key],
                )

            except (
                ValueError,
                PermissionError,
                ZoneInfoNotFoundError,
            ):
                st.error(
                    "The interview could not be saved. "
                    "Check its date, time zone and application status."
                )

            else:
                st.session_state.pop(
                    token_key,
                    None,
                )
                st.rerun()

    if active:
        if compact:
            with st.expander(
                "Add interview round",
                expanded=False,
            ):
                create_round_form()
        else:
            create_round_form()

    def render_brief(item):
        try:
            brief = (
                preparation_service
                or InterviewPreparationService()
            ).build_brief(
                candidate_id,
                job_id,
                item.interview_id,
            )

        except (ValueError, PermissionError):
            st.warning(
                "Current evidence needs review before this brief "
                "can be prepared. Your interview history is preserved."
            )
            return

        if compact:
            st.markdown("##### About this interview")

        if brief.about_role:
            st.write(brief.about_role)

        if compact:
            st.markdown("##### Company context")

        if not brief.company_context:
            st.caption(
                "Public company context is not available."
            )
        else:
            if not compact:
                st.caption(
                    "Public source-reported company context"
                )

            for value in brief.company_context:
                st.write(value)

        for value in brief.company_uncertainties:
            st.caption(value)

        if not brief.interviewer_contexts:
            st.caption(
                "Public interviewer research is not available."
            )
        else:
            if compact:
                st.markdown("##### Interviewer context")

            for value in brief.interviewer_contexts:
                st.write(value)

        areas = (
            *brief.strongest_evidence,
            *brief.likely_areas,
        )

        if areas and compact:
            st.markdown("##### What to prepare")

        for area in areas:
            st.markdown(
                f"**{area.topic}**"
            )
            st.write(area.guidance)

            if area.caution:
                st.caption(area.caution)

        if brief.previous_round_feedback:
            st.markdown(
                "**Recorded feedback from earlier rounds**"
            )

            for value in brief.previous_round_feedback:
                st.write(value)

        if brief.next_stage_context:
            if compact:
                st.markdown("##### Next-round context")

            for value in brief.next_stage_context:
                st.write(value)

        if brief.questions_to_ask:
            if compact:
                st.markdown("##### Questions to ask")

            for value in brief.questions_to_ask:
                st.write(value)

    def render_round(item):
        if compact:
            if item.scheduled_at:
                st.caption(item.scheduled_at)
            else:
                st.caption(
                    "Date and time not confirmed"
                )

            details = [
                *item.interviewer_names,
                *item.interviewer_roles,
            ]

            if item.interview_type:
                details.append(item.interview_type)

            for value in details:
                if value:
                    st.write(value)

            if item.notes:
                st.caption(item.notes)

        else:
            st.markdown(
                f"#### Interview {item.sequence}"
            )

            st.write(
                item.scheduled_at
                or "Date and time not confirmed"
            )

            for value in (
                *item.interviewer_names,
                *item.interviewer_roles,
                item.interview_type,
                item.notes,
            ):
                if value:
                    st.write(value)

        feedback = repository.feedback_for(
            item.interview_id,
            candidate_id,
            job_id,
        )

        if read_only:
            if feedback is not None:
                if feedback.feedback_text:
                    st.write(
                        feedback.feedback_text
                    )

                if feedback.next_steps:
                    st.caption(
                        "Next steps: "
                        + feedback.next_steps
                    )
            else:
                st.caption(
                    "No recorded feedback for this round."
                )

        else:
            if compact:
                st.markdown("##### Round feedback")

            with st.form(
                f"round_feedback:{candidate_id}:{job_id}:{item.interview_id}"
            ):
                text = st.text_area(
                    "Feedback",
                    value=(
                        feedback.feedback_text
                        if feedback
                        else ""
                    ),
                )

                next_steps = st.text_area(
                    "Next steps",
                    value=(
                        feedback.next_steps
                        if feedback
                        else ""
                    ),
                )

                save = st.form_submit_button(
                    "Save round feedback"
                )

            if save:
                try:
                    repository.save_feedback(
                        InterviewRoundFeedback(
                            item.interview_id,
                            candidate_id,
                            job_id,
                            text,
                            next_steps,
                        )
                    )

                except (
                    ValueError,
                    PermissionError,
                ):
                    st.error(
                        "Feedback could not be saved. "
                        "Refresh and try again."
                    )

                else:
                    st.rerun()

        brief_label = (
            "Prepare for this interview"
            if compact
            else "View interview brief"
        )

        if st.button(
            brief_label,
            key=(
                f"brief:{candidate_id}:"
                f"{job_id}:{item.interview_id}"
            ),
        ):
            render_brief(item)

    for item in rounds:
        if compact:
            round_title = f"Interview {item.sequence}"

            if item.interview_type:
                round_title += (
                    f" - {item.interview_type}"
                )

            with st.expander(
                round_title,
                expanded=False,
            ):
                render_round(item)

        else:
            render_round(item)

    # Never assign unsequenced historical feedback
    # to an invented round.
    from services.interview_details_repository import (
        InterviewDetailsRepository,
    )
    from services.interview_feedback_repository import (
        InterviewFeedbackRepository,
    )

    historical = InterviewDetailsRepository().get(
        candidate_id,
        job_id,
    )

    old_feedback = InterviewFeedbackRepository().get(
        candidate_id,
        job_id,
    )

    if historical or old_feedback:
        if compact:
            with st.expander(
                "Historical interview records",
                expanded=False,
            ):
                if historical:
                    for value in (
                        historical.scheduled_at,
                        historical.interviewer,
                        historical.instructions,
                    ):
                        if value:
                            st.write(value)

                if old_feedback:
                    for value in (
                        old_feedback.recruiter_feedback,
                        old_feedback.candidate_notes,
                        old_feedback.next_stage_instructions,
                    ):
                        if value:
                            st.write(value)

        else:
            st.caption(
                "Historical interview records "
                "(not assigned to a round)"
            )

            if historical:
                for value in (
                    historical.scheduled_at,
                    historical.interviewer,
                    historical.instructions,
                ):
                    if value:
                        st.write(value)

            if old_feedback:
                for value in (
                    old_feedback.recruiter_feedback,
                    old_feedback.candidate_notes,
                    old_feedback.next_stage_instructions,
                ):
                    if value:
                        st.write(value)



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
    source_type: str = ""
    gap_type: str = ""
    source_label: str = ""
    what_to_demonstrate: str = ""
    example_direction: str = ""
    emphasis: str = ""
    caution: str = ""
    category: str = "prepare"


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
    evidence_examples: list[str] = field(default_factory=list)
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
            source_type=area.source_type,
            gap_type=area.gap_type,
            source_label=_area_source_label(area.source_type),
            what_to_demonstrate=area.what_to_demonstrate,
            example_direction=area.example_direction,
            emphasis=area.emphasis,
            caution=area.caution,
            category=(
                "gap"
                if (
                    area.source_type
                    in {"structural_gap", "development_gap"}
                    or area.gap_type
                )
                else "prepare"
            ),
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
        evidence_examples=list(
            dict.fromkeys(
                " ".join(str(item.statement or "").split())
                for item in context.authorized_evidence
                if (
                    item.authority != "developing_evidence"
                    and item.source_type
                    in {
                        "professional_experience",
                        "career_update",
                    }
                    and str(item.statement or "").strip()
                )
            )
        ),
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




def load_company_profile_for_interview(
    company_name,
    *,
    company_repository=None,
    profile_repository=None,
):
    """
    Read the exact persisted company identity and current public
    profile. This function performs no research and no writes.
    """
    from services.company_profile_repository import (
        CompanyProfileRepository,
    )
    from services.company_repository import (
        CompanyRepository,
    )

    company_name = " ".join(
        str(company_name or "").split()
    )

    if not company_name:
        return None, None

    company_repository = (
        company_repository
        or CompanyRepository()
    )

    profile_repository = (
        profile_repository
        or CompanyProfileRepository()
    )

    company = company_repository.find_company(
        company_name
    )

    if company is None:
        return None, None

    profile = profile_repository.current(
        company.id
    )

    return company, profile


def _render_company_brief(
    st,
    *,
    company_name,
    role,
    candidate_id,
    job_id,
    read_only=False,
    company_repository=None,
    profile_repository=None,
    research_service=None,
):
    st.markdown("#### Company brief")

    company, profile = (
        load_company_profile_for_interview(
            company_name,
            company_repository=company_repository,
            profile_repository=profile_repository,
        )
    )

    if profile is not None:
        if profile.what_they_do:
            st.write(
                profile.what_they_do
            )

        if profile.size_context:
            st.caption(
                profile.size_context
            )

        sections = (
            (
                "Services",
                profile.products_services[:3],
            ),
            (
                "Strategy and priorities",
                profile.public_strategy_priorities[:3],
            ),
            (
                "Recent developments",
                profile.recent_developments[:3],
            ),
        )

        def render_company_context():
            for title, values in sections:
                values = [
                    value
                    for value in values
                    if str(value or "").strip()
                ]

                if not values:
                    continue

                st.markdown(
                    f"##### {title}"
                )

                for value in values:
                    st.markdown(
                        f"- {value}"
                    )

            if profile.uncertainties:
                st.markdown(
                    "##### What to verify"
                )

                for value in profile.uncertainties[:4]:
                    st.markdown(
                        f"- {value}"
                    )

        has_company_context = bool(
            any(
                str(value or "").strip()
                for _, values in sections
                for value in values
            )
            or profile.uncertainties
        )

        if has_company_context:
            expander = getattr(
                st,
                "expander",
                None,
            )

            if expander is not None:
                with expander(
                    "Explore company context",
                    expanded=False,
                ):
                    render_company_context()
            else:
                render_company_context()

        if profile.sources:
            def render_sources():
                for item in profile.sources[:6]:
                    label = (
                        str(
                            item.title
                            or item.ref
                        )
                        .replace("[", "")
                        .replace("]", "")
                    )

                    st.markdown(
                        f"- [{label}]({item.ref})"
                    )

                if len(profile.sources) > 6:
                    st.caption(
                        f"{len(profile.sources) - 6} "
                        "more public sources saved."
                    )

            expander = getattr(
                st,
                "expander",
                None,
            )

            if expander is not None:
                with expander(
                    "Public sources",
                    expanded=False,
                ):
                    render_sources()
            else:
                st.markdown(
                    "##### Public sources"
                )
                render_sources()

        return profile

    st.caption(
        "Public company research is not available yet."
    )

    if read_only or not company_name:
        return None

    button = getattr(
        st,
        "button",
        None,
    )

    if button is None:
        return None

    if button(
        "Research company",
        key=(
            f"research_company:"
            f"{candidate_id}:{job_id}"
        ),
    ):
        try:
            service = research_service

            if service is None:
                from services.company_research_service import (
                    CompanyResearchService,
                )

                service = CompanyResearchService()

            profile = service.build_if_missing(
                company_name=company_name,
                job_title=role,
            )

        except Exception:
            st.warning(
                "Company research could not be completed "
                "right now. Please try again."
            )
            return None

        if profile is None:
            st.warning(
                "WorkPilot could not build a grounded "
                "company brief from public sources."
            )
            return None

        rerun = getattr(
            st,
            "rerun",
            None,
        )

        if rerun is not None:
            rerun()

        return profile

    return None


def render_interview_preparation_overview(
    st,
    *,
    candidate_id,
    job_id,
    lifecycle_status,
    context_service=None,
    preparation_service=None,
    details_repository=None,
    feedback_repository=None,
    read_only=False,
    company_repository=None,
    company_profile_repository=None,
    company_research_service=None,
):
    """
    Compact deterministic interview preparation.

    Company research is read from a persisted public snapshot.
    Network research only runs after an explicit user action.
    """
    result = load_interview_preparation_view(
        candidate_id=candidate_id,
        job_id=job_id,
        lifecycle_status=lifecycle_status,
        context_service=context_service,
        preparation_service=preparation_service,
        details_repository=details_repository,
        feedback_repository=feedback_repository,
    )

    if result.error_message:
        st.warning(
            result.error_message
        )
        return result

    if (
        not result.visible
        or result.view is None
    ):
        return result

    view = result.view

    _render_company_brief(
        st,
        company_name=view.company,
        role=view.role,
        candidate_id=candidate_id,
        job_id=job_id,
        read_only=read_only,
        company_repository=company_repository,
        profile_repository=company_profile_repository,
        research_service=company_research_service,
    )

    divider = getattr(
        st,
        "divider",
        None,
    )

    if divider is not None:
        divider()

    def render_preparation_content():
        class _InlineSection:
            def __init__(self, label):
                self.label = label

            def __enter__(self):
                st.markdown(
                    f"##### {self.label}"
                )
                return self

            def __exit__(
                self,
                exc_type,
                exc,
                traceback,
            ):
                return False

        section_expander = getattr(
            st,
            "expander",
            None,
        )

        if section_expander is None:
            section_expander = (
                lambda label, expanded=False:
                _InlineSection(label)
            )
        if view.summary_guidance:
            st.write(
                view.summary_guidance
            )

        metadata = [
            value
            for value in (
                view.interview_type,
                view.interview_format,
                view.interviewer,
                view.duration,
                view.scheduled_at,
            )
            if value
        ]

        if metadata:
            st.caption(
                " | ".join(metadata)
            )

        if view.interview_instructions:
            with section_expander("Interview details", expanded=False):
                for value in view.interview_instructions:
                    st.markdown(
                        f"- {value}"
                    )
        core_topics = [
            area
            for area in view.preparation_areas
            if (
                area.category == "prepare"
                and area.source_type
                in {
                    "core_requirement",
                    "explicit_interview_topic",
                }
            )
        ]

        positioning = [
            area
            for area in view.preparation_areas
            if (
                area.category == "prepare"
                and area.source_type
                == "positioning_theme"
            )
        ]

        # Transitional/unknown prepare categories remain visible
        # without being promoted to core requirements.
        other_prepare = [
            area
            for area in view.preparation_areas
            if (
                area.category == "prepare"
                and area
                not in core_topics
                and area
                not in positioning
            )
        ]

        if core_topics:
            with section_expander("Core topics", expanded=False):
                for area in core_topics:
                    st.markdown(
                        f"- {area.topic}"
                    )

                st.caption(
                    "For each topic, choose a real situation, "
                    "explain what you did, and what happened. "
                    "If you do not have direct experience, say so "
                    "and use genuine adjacent experience."
                )
        if positioning:
            with section_expander("Useful positioning", expanded=False):
                for area in positioning:
                    st.markdown(
                        f"- {area.topic}"
                    )
        if other_prepare:
            with section_expander("Additional topics", expanded=False):
                for area in other_prepare:
                    st.markdown(
                        f"- {area.topic}"
                    )
        if view.evidence_examples:
            with section_expander("Evidence you can draw from", expanded=False):
                st.caption(
                    "Confirmed examples from your profile. "
                    "Use only the evidence that genuinely supports the topic "
                    "you are discussing."
                )

                def compact_evidence(value):
                    value = " ".join(
                        str(value or "").split()
                    )

                    if len(value) <= 180:
                        return value

                    return (
                        value[:177].rstrip()
                        + "..."
                    )

                for value in view.evidence_examples[:3]:
                    st.markdown(
                        f"- {compact_evidence(value)}"
                    )

                remaining_evidence = (
                    len(view.evidence_examples) - 3
                )

                if remaining_evidence > 0:
                    st.caption(
                        f"{remaining_evidence} more confirmed examples "
                        "are available in your profile."
                    )
        gaps = [
            area
            for area in view.preparation_areas
            if area.category == "gap"
        ]

        if gaps:
            with section_expander("Areas to handle carefully", expanded=False):
                developing = [
                    area
                    for area in gaps
                    if area.gap_type
                    in {
                        "development",
                        "developing_evidence",
                        "transferable",
                    }
                ]

                limited = [
                    area
                    for area in gaps
                    if area not in developing
                ]

                if developing:
                    st.markdown(
                        "**Developing or transferable**"
                    )

                    for area in developing:
                        st.markdown(
                            f"- {area.topic}"
                        )

                if limited:
                    st.markdown(
                        "**Limited direct evidence**"
                    )

                    for area in limited:
                        st.markdown(
                            f"- {area.topic}"
                        )

                st.caption(
                    "Keep the boundary clear: use genuine adjacent "
                    "experience where it exists, but do not turn "
                    "learning or transferable experience into claimed "
                    "production expertise."
                )
        if view.rehearsal_prompts:
            with section_expander("Practice", expanded=False):
                st.caption(
                    "Choose a few topics and prepare a truthful example using "
                    "situation - what you did - result. If you do not have "
                    "direct experience, use genuine adjacent experience."
                )

                def compact_practice_prompt(value):
                    value = " ".join(
                        str(value or "").split()
                    )

                    prefix = (
                        "Prepare to discuss a real example related to "
                    )

                    if value.startswith(prefix):
                        value = value[len(prefix):]

                    return value.rstrip(".")

                visible_prompts = (
                    view.rehearsal_prompts[:3]
                )

                for value in visible_prompts:
                    st.markdown(
                        f"- {compact_practice_prompt(value)}"
                    )

                remaining_prompts = (
                    len(view.rehearsal_prompts) - len(visible_prompts)
                )

                if remaining_prompts > 0:
                    st.caption(
                        f"{remaining_prompts} more practice topics "
                        "are covered by the core topics above."
                    )
        if view.questions_to_ask_the_company:
            with section_expander("Questions to ask", expanded=False):
                for value in (
                    view.questions_to_ask_the_company
                ):
                    st.markdown(
                        f"- {value}"
                    )
        carry_forward = bool(
            view.recruiter_feedback
            or view.candidate_self_reports
            or view.previously_discussed_topics
            or view.review_topics
            or view.next_stage_instructions
        )

        if carry_forward:
            with section_expander("Carry forward", expanded=False):
                for value in view.recruiter_feedback:
                    st.markdown(
                        f"- Recruiter feedback: {value}"
                    )

                for value in view.candidate_self_reports:
                    st.markdown(
                        f"- Your note: {value}"
                    )

                for value in (
                    view.previously_discussed_topics
                ):
                    st.markdown(
                        f"- Previously discussed: {value}"
                    )

                for value in view.review_topics:
                    st.markdown(
                        f"- Review again: {value}"
                    )

                for value in (
                    view.next_stage_instructions
                ):
                    st.markdown(
                        f"- Next-stage instruction: {value}"
                    )

    st.markdown(
        "#### Prepare for your interview"
    )

    render_preparation_content()

    return result

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
