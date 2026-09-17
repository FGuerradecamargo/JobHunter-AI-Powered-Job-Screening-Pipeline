from __future__ import annotations

from dataclasses import replace
from services.job_evidence_constraints import validate_evidence_requirement
from services.temporal_applicability import resolve_temporal_applicability

from models.hiring_case import HiringCaseInput, RequirementAssessment, RequirementEvidenceState
from models.profile_interpretation import (
    AIJobProfileSnapshot,
    CandidateProfileSnapshot,
    HiringCaseInterpretation,
    InterpretationAuthority,
    JobHardFacts,
)


def build_profile_hiring_case_input(
    *,
    candidate_profile: CandidateProfileSnapshot,
    job_profile: AIJobProfileSnapshot,
    hard_facts: JobHardFacts,
    interpretation: HiringCaseInterpretation,
    hard_assessments: tuple[RequirementAssessment, ...] = (),
) -> HiringCaseInput:
    if job_profile.job_id != hard_facts.job_id:
        raise PermissionError("Job profile and hard facts are not scoped to the same job.")
    if job_profile.job_signature != hard_facts.job_signature:
        raise ValueError("Job profile is stale for the supplied hard facts.")
    needs = {item.need_id: item for item in job_profile.needs}
    links = {item.need_id: item for item in interpretation.requirement_links}
    hard = {item.requirement_id: item for item in hard_assessments}
    unknown_links = set(links) - set(needs)
    if unknown_links:
        raise ValueError("Hiring Case interpretation cited an unknown job need.")
    valid_evidence = set(candidate_profile.source_refs)
    confirmed_gaps = {item.casefold() for item in candidate_profile.confirmed_gaps}
    requirements = []
    for need in job_profile.needs:
        validate_evidence_requirement(need, hard_facts)
        if need.need_id in hard:
            assessment = hard[need.need_id]
            if not set(assessment.evidence_refs).issubset(valid_evidence):
                raise ValueError("Hard assessment cited unknown candidate evidence.")
            requirements.append(replace(assessment, evidence_requirement=need.evidence_requirement,
                temporal_requirement=need.temporal_requirement,
                temporal_applicability=resolve_temporal_applicability(need, hard_facts, assessment.evidence_refs, interpretation.temporal_evidence)))
            continue
        link = links.get(need.need_id)
        if link is None:
            state = RequirementEvidenceState.EVIDENCE_MISSING
            refs: list[str] = []
            rationale = "No grounded evidence relationship was supplied."
            defensible = False
        else:
            if not set(link.evidence_refs).issubset(valid_evidence):
                raise ValueError("Hiring Case interpretation cited unknown candidate evidence.")
            state = link.evidence_state
            refs = list(link.evidence_refs)
            rationale = link.rationale
            defensible = link.interview_defensible
            if state in {RequirementEvidenceState.PROVEN, RequirementEvidenceState.TRANSFERABLE} and not refs:
                state = RequirementEvidenceState.EVIDENCE_MISSING
                defensible = False
            if state is RequirementEvidenceState.GAP and (
                need.need_id.casefold() not in confirmed_gaps
                and need.label.casefold() not in confirmed_gaps
            ):
                state = RequirementEvidenceState.EVIDENCE_MISSING
                defensible = False
        requirements.append(RequirementAssessment(
            requirement_id=need.need_id,
            requirement=need.label,
            importance=need.importance,
            evidence_state=state,
            evidence_refs=refs,
            rationale=rationale,
            interview_defensible=defensible and bool(refs),
            evidence_requirement=need.evidence_requirement,
            temporal_requirement=need.temporal_requirement,
            temporal_applicability=resolve_temporal_applicability(need, hard_facts, refs, interpretation.temporal_evidence),
        ))
    hard_blockers = sorted({
        fact.value for fact in hard_facts.facts if fact.hard_blocker
    } | {
        need.label for need in job_profile.needs
        if need.hard_blocker and need.authority is InterpretationAuthority.EXPLICIT
    })
    return HiringCaseInput(
        candidate_id=candidate_profile.candidate_id,
        job_id=job_profile.job_id,
        requirements=requirements,
        opportunity_signals=list(interpretation.opportunity_signals),
        hard_eligibility_blockers=hard_blockers,
        seniority_context_mismatch=interpretation.seniority_context_mismatch,
    )
