from __future__ import annotations

from dataclasses import asdict
import re

from models.interview_context import InterviewContext
from models.interview_feedback import InterviewFeedback
from models.interview_preparation import (
    InterviewFeedbackGuidance,
    InterviewPreparation,
    PreparationArea,
)
from services.career_memory_source_builder import build_source_signature


INTERVIEW_PREPARATION_SCHEMA_VERSION = "interview-preparation-v1"


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _key(value) -> str:
    return _text(value).casefold()


def _canonical(value):
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple, set)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: build_source_signature({"item": item}))
    if isinstance(value, str):
        return _key(value)
    return value


def _evidence_index(context: InterviewContext):
    result = {}
    for item in sorted(context.authorized_evidence, key=lambda value: value.evidence_ref):
        if _key(item.statement):
            result.setdefault(_key(item.statement), []).append(item)
    return result


def _area_for_topic(topic: str, source_type: str, context, evidence_by_text):
    normalized = _text(topic)
    matches = evidence_by_text.get(_key(topic), [])
    proven = [item for item in matches if item.authority != "developing_evidence"]
    evidence = (proven or matches or [None])[0]
    evidence_refs = [item.evidence_ref for item in matches]
    developing = bool(matches and not proven)

    priority = "explicit" if source_type == "explicit_interview_topic" else "normal"
    if source_type == "core_requirement" and evidence and not developing:
        priority = "high"

    source_labels = {
        "core_requirement": "The role identifies this as a core requirement.",
        "explicit_interview_topic": "The interview details explicitly mention this topic.",
    }
    if evidence and not developing:
        demonstrate = (
            "Use the authorized evidence linked to this area and explain the real "
            "scope, actions, and outcome accurately."
        )
        direction = (
            f"Review the real experience recorded as '{_text(evidence.statement)}' "
            "and select concrete details you can verify."
        )
        caution = "Keep every claim within the scope of the linked evidence."
    elif developing:
        demonstrate = (
            "Describe your current level accurately, including what you can do today "
            "and what remains in development."
        )
        direction = (
            "Look for a real learning or practice example without presenting it as "
            "production expertise."
        )
        caution = "This evidence is developing; do not present it as proven expertise."
    else:
        demonstrate = (
            "Identify whether you have a real example that demonstrates this capability."
        )
        direction = (
            "Look across your real experience for a situation, action, and outcome "
            "that relate directly to this topic."
        )
        caution = "No authorized evidence is linked; do not imply experience you cannot support."

    return PreparationArea(
        topic=normalized,
        source_type=source_type,
        priority=priority,
        what_they_seek=source_labels[source_type],
        what_to_demonstrate=demonstrate,
        example_direction=direction,
        emphasis=(
            "Explain ownership, decisions, tradeoffs, and impact."
            if context.interview_stage == "final_interview"
            else "Explain the relevant capability and the evidence behind it."
        ),
        caution=caution,
        evidence_refs=evidence_refs,
        gap_type="developing_evidence" if developing else "",
        gap_text=_text(evidence.statement) if developing else "",
    )


def _gap_area(gap: str, structural: bool) -> PreparationArea:
    gap = _text(gap)
    if structural:
        return PreparationArea(
            topic=gap,
            source_type="structural_gap",
            priority="high",
            what_they_seek="The opportunity includes a capability not supported by current evidence.",
            what_to_demonstrate=(
                "Explain the boundary honestly, then discuss only genuine adjacent or "
                "transferable experience."
            ),
            example_direction=(
                "Identify real adjacent knowledge and a concrete, credible plan to close the gap."
            ),
            emphasis="Be precise about what you have and have not done.",
            caution="Do not imply experience or production exposure that the evidence does not support.",
            gap_type="structural",
            gap_text=gap,
        )
    return PreparationArea(
        topic=gap,
        source_type="development_gap",
        priority="high",
        what_they_seek="This area may require stronger or deeper capability.",
        what_to_demonstrate=(
            "Describe your current level accurately, what you can do today, and what "
            "you are actively learning."
        ),
        example_direction="Prepare a truthful example of current practice or learning progress.",
        emphasis="Show self-awareness and a practical development approach.",
        caution="Do not present a developing capability as established expertise.",
        gap_type="development",
        gap_text=gap,
    )


def _interview_instructions(context: InterviewContext) -> list[str]:
    instructions = []
    if context.instructions.strip():
        instructions.append(context.instructions.strip())
    if context.interview_format:
        instructions.append(f"Use the supplied interview format: {_text(context.interview_format)}.")
    if context.interview_type:
        instructions.append(f"Prepare for the supplied interview type: {_text(context.interview_type)}.")
    if context.interviewer:
        instructions.append(f"Interviewer information supplied: {_text(context.interviewer)}.")
    if context.duration_minutes is not None:
        instructions.append(
            f"The supplied duration is {context.duration_minutes} minutes; select evidence that fits this time."
        )
    if context.scheduled_at:
        instructions.append(f"Scheduled time supplied: {_text(context.scheduled_at)}.")
    return instructions


def build_interview_preparation(
    context: InterviewContext,
    feedback: InterviewFeedback | None = None,
) -> InterviewPreparation:
    if not context.candidate_id or not context.job_id or not context.source_signature:
        raise ValueError("Interview Context is incomplete.")
    if context.interview_stage not in {"interview", "final_interview"}:
        raise ValueError("Interview Context is not in an active interview stage.")
    if feedback is not None and feedback.candidate_id != context.candidate_id:
        raise PermissionError("Interview feedback belongs to another candidate.")
    if feedback is not None and feedback.job_id != context.job_id:
        raise PermissionError("Interview feedback belongs to another job.")
    if feedback is not None and feedback.interview_stage not in {
        "interview", "final_interview"
    }:
        raise PermissionError("Interview feedback has an invalid stage scope.")

    evidence_by_text = _evidence_index(context)
    areas = [
        _area_for_topic(topic, "explicit_interview_topic", context, evidence_by_text)
        for topic in sorted({_text(v) for v in context.explicit_topics if _text(v)}, key=str.casefold)
    ]
    areas.extend(
        _area_for_topic(topic, "core_requirement", context, evidence_by_text)
        for topic in sorted({_text(v) for v in context.core_requirements if _text(v)}, key=str.casefold)
    )

    valid_refs = {item.evidence_ref for item in context.authorized_evidence}
    for theme in sorted(context.positioning_themes, key=lambda item: _key(item.theme)):
        refs = sorted(set(theme.evidence_refs) & valid_refs)
        if not refs:
            continue
        areas.append(
            PreparationArea(
                topic=_text(theme.theme),
                source_type="positioning_theme",
                priority="normal",
                what_they_seek="This evidence-backed theme is relevant to positioning for the role.",
                what_to_demonstrate="Explain the real evidence supporting this theme.",
                example_direction="Review the linked evidence and select verifiable actions and outcomes.",
                emphasis="Connect the theme to the opportunity without expanding the underlying facts.",
                caution="Keep claims within the linked authorized evidence.",
                evidence_refs=refs,
            )
        )
    areas.extend(_gap_area(gap, False) for gap in sorted(context.development_gaps, key=_key))
    areas.extend(_gap_area(gap, True) for gap in sorted(context.structural_gaps, key=_key))

    summary = (
        "Prepare decision-level examples focused on ownership, impact, tradeoffs, and role fit."
        if context.interview_stage == "final_interview"
        else "Prepare broad, truthful examples that demonstrate relevant capabilities and evidence."
    )
    questions = [
        f"What would success in the first months of the {_text(context.job_title) or 'role'} look like?",
        "Which teams and stakeholders does this role work with most closely?",
        "What are the most important priorities and challenges for this role?",
    ]
    rehearsals = [
        f"Prepare to discuss a real example related to {_text(area.topic)}."
        for area in areas
        if area.source_type in {"core_requirement", "explicit_interview_topic"}
    ]
    explicit_feedback = []
    discussed_topics = []
    review_topics = []
    next_stage_instructions = []
    if feedback is not None:
        if feedback.recruiter_feedback.strip():
            explicit_feedback.append(
                InterviewFeedbackGuidance(
                    source_type="recruiter_feedback",
                    text=feedback.recruiter_feedback.strip(),
                    guidance=(
                        "Address this explicit recruiter feedback using only real, "
                        "authorized examples; do not treat it as a causal conclusion."
                    ),
                )
            )
        if feedback.candidate_notes.strip():
            explicit_feedback.append(
                InterviewFeedbackGuidance(
                    source_type="candidate_self_report",
                    text=feedback.candidate_notes.strip(),
                    guidance=(
                        "Use this self-report to guide review, without treating it as "
                        "a verified professional fact."
                    ),
                )
            )
        discussed_topics = sorted(
            {_text(value) for value in feedback.discussed_topics if _text(value)},
            key=str.casefold,
        )
        review_topics = sorted(
            {_text(value) for value in feedback.difficult_topics if _text(value)},
            key=str.casefold,
        )
        if feedback.next_stage_instructions.strip():
            next_stage_instructions = [feedback.next_stage_instructions.strip()]
    signature_payload = _canonical(
        {
            "schema_version": INTERVIEW_PREPARATION_SCHEMA_VERSION,
            "context_signature": context.source_signature,
            "stage": context.interview_stage,
            "context_material": {
                "requirements": context.core_requirements,
                "topics": context.explicit_topics,
                "instructions": context.instructions,
                "details": [context.interview_type, context.interview_format, context.interviewer,
                            context.duration_minutes, context.scheduled_at],
                "evidence": [asdict(item) for item in context.authorized_evidence],
                "themes": [asdict(item) for item in context.positioning_themes],
                "development_gaps": context.development_gaps,
                "structural_gaps": context.structural_gaps,
                "feedback": (
                    {
                        "stage": feedback.interview_stage,
                        "recruiter_feedback": feedback.recruiter_feedback,
                        "candidate_notes": feedback.candidate_notes,
                        "discussed_topics": feedback.discussed_topics,
                        "difficult_topics": feedback.difficult_topics,
                        "next_stage_instructions": feedback.next_stage_instructions,
                    }
                    if feedback is not None
                    else None
                ),
            },
        }
    )
    return InterviewPreparation(
        candidate_id=context.candidate_id,
        job_id=context.job_id,
        analysis_id=context.analysis_id,
        interview_context_signature=context.source_signature,
        interview_stage=context.interview_stage,
        summary_guidance=summary,
        preparation_areas=areas,
        interview_instructions=_interview_instructions(context),
        questions_to_ask_the_company=questions,
        rehearsal_prompts=rehearsals,
        explicit_feedback=explicit_feedback,
        previously_discussed_topics=discussed_topics,
        review_topics=review_topics,
        next_stage_instructions=next_stage_instructions,
        source_signature=build_source_signature(signature_payload),
        schema_version=INTERVIEW_PREPARATION_SCHEMA_VERSION,
    )
