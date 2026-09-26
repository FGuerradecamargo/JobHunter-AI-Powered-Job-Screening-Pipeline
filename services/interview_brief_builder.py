from __future__ import annotations
from dataclasses import asdict
import hashlib
import json

from models.application_tracking import (
    InterviewRound,
    InterviewRoundFeedback,
)
from models.company_profile import CompanyProfileSnapshot
from models.interview_brief import (
    InterviewBrief,
    InterviewBriefArea,
    InterviewerPublicContext,
)
from models.interview_preparation import InterviewPreparation


def _area(item) -> InterviewBriefArea:
    return InterviewBriefArea(
        topic=item.topic,
        guidance=item.what_to_demonstrate,
        evidence_refs=tuple(item.evidence_refs),
        caution=item.caution,
    )


def build_interview_brief(
    *,
    preparation: InterviewPreparation,
    interview_round: InterviewRound,
    company_profile: CompanyProfileSnapshot | None = None,
    interviewer_contexts: tuple[InterviewerPublicContext, ...] = (),
    previous_feedback: tuple[InterviewRoundFeedback, ...] = (),
    previous_rounds: tuple[InterviewRound, ...] = (),
    expected_company_id: str = "",
) -> InterviewBrief:
    if (
        preparation.candidate_id != interview_round.candidate_id
        or preparation.job_id != interview_round.job_id
    ):
        raise PermissionError(
            "Interview preparation and round belong to different scopes."
        )

    rounds = {item.interview_id: item for item in previous_rounds}
    for feedback in previous_feedback:
        if (
            feedback.candidate_id != interview_round.candidate_id
            or feedback.job_id != interview_round.job_id
        ):
            raise PermissionError(
                "Previous interview feedback belongs to another scope."
            )
        prior = rounds.get(feedback.interview_id)
        if (prior is None or prior.candidate_id != interview_round.candidate_id
                or prior.job_id != interview_round.job_id or prior.sequence >= interview_round.sequence):
            raise ValueError("Feedback must belong to a verified earlier interview round.")

    for person in interviewer_contexts:
        if ((person.name and person.name.casefold() not in {n.casefold() for n in interview_round.interviewer_names})
                or (not person.name and person.role.casefold() not in {r.casefold() for r in interview_round.interviewer_roles})):
            raise ValueError("Interviewer context does not match this round.")

    company_context = ()
    company_version = None
    if company_profile is not None:
        if not expected_company_id or company_profile.company_id != expected_company_id:
            raise PermissionError("Company context does not match the selected company.")
        company_version = company_profile.profile_version
        company_context = tuple(
            value
            for value in (
                company_profile.what_they_do,
                *company_profile.products_services[:2],
                *company_profile.market_context[:2],
                *company_profile.public_strategy_priorities[:2],
                *company_profile.recent_developments[:2],
            )
            if value
        )

    evidence_areas = [
        item
        for item in preparation.preparation_areas
        if item.evidence_refs and not item.gap_type
    ]
    likely_areas = [
        item
        for item in preparation.preparation_areas
        if item.source_type in {
            "core_requirement",
            "explicit_interview_topic",
            "development_gap",
            "structural_gap",
        }
    ]

    feedback_text = []
    next_context = []
    for feedback in sorted(
        previous_feedback,
        key=lambda item: rounds[item.interview_id].sequence,
    ):
        if feedback.feedback_text:
            feedback_text.append(feedback.feedback_text)
        if feedback.next_steps:
            next_context.append(feedback.next_steps)

    signature = hashlib.sha256(json.dumps({
        "preparation": asdict(preparation), "round": asdict(interview_round),
        "company": asdict(company_profile) if company_profile else None,
        "interviewers": [asdict(item) for item in interviewer_contexts],
        "feedback": [asdict(item) for item in sorted(previous_feedback, key=lambda item: item.interview_id)],
        "previous_rounds": [asdict(rounds[item.interview_id]) for item in sorted(previous_feedback, key=lambda item: item.interview_id)],
    }, sort_keys=True).encode()).hexdigest()
    return InterviewBrief(
        candidate_id=interview_round.candidate_id,
        job_id=interview_round.job_id,
        interview_id=interview_round.interview_id,
        round_sequence=interview_round.sequence,
        scheduled_at=interview_round.scheduled_at,
        base_preparation_signature=preparation.source_signature,
        company_profile_version=company_version,
        company_id=company_profile.company_id if company_profile else "",
        company_source_signature=company_profile.source_signature if company_profile else "",
        company_claims=tuple(claim for claim in company_profile.claims if claim.value in company_context) if company_profile else (),
        company_uncertainties=company_profile.uncertainties if company_profile else (),
        previous_round_refs=tuple(item.interview_id for item in sorted(previous_feedback, key=lambda item: rounds[item.interview_id].sequence)),
        source_signature=signature,
        about_role=preparation.summary_guidance,
        company_context=company_context,
        strongest_evidence=tuple(
            _area(item)
            for item in evidence_areas[:5]
        ),
        likely_areas=tuple(
            _area(item)
            for item in likely_areas[:8]
        ),
        interviewer_contexts=tuple(interviewer_contexts),
        questions_to_ask=tuple(
            preparation.questions_to_ask_the_company[:5]
        ),
        previous_round_feedback=tuple(feedback_text),
        next_stage_context=tuple(next_context),
    )
