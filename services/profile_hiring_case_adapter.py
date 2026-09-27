from __future__ import annotations

from dataclasses import replace
from models.hiring_case import OpportunitySignalKind
from models.structured_interpretation import (
    StructuredInterpretationInput, InterpretationOperation, RegisteredSourceRef,
    SourceRefClass, OpportunityFact, FactState,
)
from services.job_evidence_constraints import validate_evidence_requirement
from services.temporal_applicability import resolve_temporal_applicability

from models.hiring_case import HiringCaseInput, RequirementAssessment, RequirementEvidenceState
from models.profile_interpretation import (
    AIJobProfileSnapshot,
    CandidateProfileSnapshot,
    HiringCaseInterpretation,
    InterpretationAuthority,
    JobHardFacts,
    HardJobFact,
    CredentialStatus,
    JobRequirementStatus,
    RequirementSubstitutability,
    CandidatePreferenceSemantic,
)


def build_hiring_interpretation_request(*, candidate_profile, source_evidence, job_profile, hard_facts):
    """Trusted refs and literal candidate preferences, not generated memory claims."""
    registry = tuple(RegisteredSourceRef(source.ref, SourceRefClass.CAREER_MEMORY_SOURCE,
        candidate_profile.candidate_id, source.source_type,
        source.source_type in {"professional_experience", "career_update"}) for source in source_evidence)
    registry += tuple(RegisteredSourceRef(fact.fact_id, SourceRefClass.JOB_HARD_FACT,
        hard_facts.job_id, fact.kind) for fact in hard_facts.facts)
    preference_fields = {
        OpportunitySignalKind.CAREER_DIRECTION: {"desired_next_work"},
        OpportunitySignalKind.ROLE_CONTENT: {"enjoyed_work", "avoid_work"},
        OpportunitySignalKind.GROWTH: {"development_interests"},
        OpportunitySignalKind.STRATEGIC_VALUE: {"career_priorities"},
    }
    job_refs = tuple(fact.fact_id for fact in hard_facts.facts)
    job_values = tuple(f"{fact.kind}: {fact.value}" for fact in hard_facts.facts)
    values = []
    for kind in OpportunitySignalKind:
        preferences = [source for source in source_evidence if source.source_type == "candidate_preference"
                       and source.ref.rsplit(":", 1)[-1] in preference_fields.get(kind, set())]
        known = bool(preferences and job_refs)
        values.append(OpportunityFact(kind, FactState.KNOWN if known else FactState.UNKNOWN,
            tuple(source.ref for source in preferences) + job_refs if known else (),
            tuple(source.summary for source in preferences) + job_values if known else ()))
    return StructuredInterpretationInput(
        operation=InterpretationOperation.ANALYZE_HIRING_CASE,
        candidate_id=candidate_profile.candidate_id, job_id=job_profile.job_id,
        memory_signature=candidate_profile.memory_signature,
        memory_projection={"sources": [{"ref": source.ref, "text": source.summary} for source in source_evidence]},
        source_registry=registry, candidate_profile=candidate_profile,
        job_profile=job_profile, hard_facts=hard_facts, opportunity_facts=tuple(values),
    )


def _finite_requirement_state(
    candidate: CandidateProfileSnapshot, fact: HardJobFact,
) -> tuple[RequirementEvidenceState, list[str]] | None:
    """Resolve exact finite facts; unknown status or conflicting records stay unknown.

    Work-authorization values are jurisdictions, language/licence values are names.
    Prose requirements need structured interpretation; substring matching is unsafe.
    """
    dimension = {
        "work_authorization": "work_authorizations",
        "language": "languages",
        "licence": "licences",
    }.get(fact.kind)
    if fact.kind in {"relocation", "night_work"}:
        constraints = [item for item in candidate.structured_preferences
                       if item.kind == fact.kind and item.semantic is CandidatePreferenceSemantic.CONSTRAINT]
        if (candidate.can_confirm_absence("constraints") and constraints
                and all(item.value == "not_allowed" for item in constraints)
                and fact.value == "required"):
            return RequirementEvidenceState.GAP, sorted({ref for item in constraints for ref in item.evidence_refs})
        return RequirementEvidenceState.EVIDENCE_MISSING, []
    if dimension is None:
        return None
    value = " ".join(fact.value.casefold().split())
    items = getattr(candidate, dimension)
    matches = [item for item in items if " ".join(
        (item.jurisdiction if dimension == "work_authorizations" else item.name).casefold().split()
    ) == value]
    missing = (RequirementEvidenceState.EVIDENCE_MISSING, [])
    if not matches:
        if candidate.can_confirm_absence(dimension) and candidate.source_refs:
            return RequirementEvidenceState.GAP, list(candidate.source_refs)
        return missing
    states = set()
    refs = set()
    for item in matches:
        refs.update(item.evidence_refs)
        if dimension == "languages":
            states.add(RequirementEvidenceState.PROVEN)
        elif dimension == "licences":
            states.add({CredentialStatus.ACTIVE: RequirementEvidenceState.PROVEN,
                        CredentialStatus.EXPIRED: RequirementEvidenceState.GAP}.get(
                            item.status, RequirementEvidenceState.EVIDENCE_MISSING))
        else:
            status = item.status.strip().casefold()
            states.add({
                "authorized": RequirementEvidenceState.PROVEN,
                "compatible": RequirementEvidenceState.PROVEN,
                "active": RequirementEvidenceState.PROVEN,
                "unauthorized": RequirementEvidenceState.GAP,
                "incompatible": RequirementEvidenceState.GAP,
                "denied": RequirementEvidenceState.GAP,
            }.get(status, RequirementEvidenceState.EVIDENCE_MISSING))
    # Conflicting or incomplete evidence needs clarification, not rejection.
    if len(states) != 1 or RequirementEvidenceState.EVIDENCE_MISSING in states:
        return missing
    state = next(iter(states))
    if state is RequirementEvidenceState.GAP and not candidate.can_confirm_absence(dimension):
        return missing
    return state, sorted(refs)


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
    # Mandatory source facts can exist before an interpreter supplies a need.
    # They still require candidate-side proof; the global hard_blocker flag is not proof.
    hard_blockers = [fact.value for fact in hard_facts.facts if (
        fact.requirement_status is JobRequirementStatus.REQUIRED
        and fact.substitutability is RequirementSubstitutability.NON_SUBSTITUTABLE
        and (resolved := _finite_requirement_state(candidate_profile, fact)) is not None
        and resolved[0] is RequirementEvidenceState.GAP
    )]
    facts = {fact.fact_id: fact for fact in hard_facts.facts}
    for need in job_profile.needs:
        validate_evidence_requirement(need, hard_facts)
        if not set(need.hard_fact_refs).issubset(facts):
            raise ValueError("Job need cited an unknown hard-fact ref.")
        strict_facts = [facts[ref] for ref in need.hard_fact_refs if (
            need.authority is InterpretationAuthority.EXPLICIT
            and facts[ref].requirement_status is JobRequirementStatus.REQUIRED
            and facts[ref].substitutability is RequirementSubstitutability.NON_SUBSTITUTABLE
            and need.requirement_status is JobRequirementStatus.REQUIRED
            and need.substitutability is RequirementSubstitutability.NON_SUBSTITUTABLE
        )]
        finite_states = [_finite_requirement_state(candidate_profile, fact) for fact in strict_facts]
        finite_states = [result for result in finite_states if result is not None]
        if finite_states:
            states = {result[0] for result in finite_states}
            state = (RequirementEvidenceState.GAP if RequirementEvidenceState.GAP in states
                     else RequirementEvidenceState.EVIDENCE_MISSING
                     if RequirementEvidenceState.EVIDENCE_MISSING in states else RequirementEvidenceState.PROVEN)
            refs = sorted({ref for _, evidence in finite_states for ref in evidence})
            requirements.append(RequirementAssessment(
                requirement_id=need.need_id, requirement=need.label, importance=need.importance,
                evidence_state=state, evidence_refs=refs,
                rationale="Candidate source facts evaluated against the mandatory job requirement.",
                interview_defensible=state is RequirementEvidenceState.PROVEN and bool(refs),
                evidence_requirement=need.evidence_requirement,
                temporal_requirement=need.temporal_requirement,
                temporal_applicability=resolve_temporal_applicability(
                    need, hard_facts, refs, interpretation.temporal_evidence),
            ))
            if state is RequirementEvidenceState.GAP:
                hard_blockers.append(need.label)
            continue
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
    return HiringCaseInput(
        candidate_id=candidate_profile.candidate_id,
        job_id=job_profile.job_id,
        requirements=requirements,
        opportunity_signals=list(interpretation.opportunity_signals),
        hard_eligibility_blockers=sorted(set(hard_blockers)),
        seniority_context_mismatch=interpretation.seniority_context_mismatch,
        candidate_profile_version=candidate_profile.profile_version,
        job_profile_version=job_profile.profile_version,
        candidate_signature=candidate_profile.memory_signature,
        job_signature=job_profile.job_signature,
    )
