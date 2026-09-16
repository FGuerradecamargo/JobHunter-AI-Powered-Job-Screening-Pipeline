from __future__ import annotations

from models.hiring_case import (
    AddEvidenceContract,
    HiringCase,
    HiringCaseClassification,
    HiringCaseInput,
    HiringCaseStrength,
    HowToProveContract,
    OpportunityAssessment,
    OpportunityConfidence,
    OpportunitySignalState,
    OpportunityValue,
    ProofItem,
    RequirementEvidenceState,
    RequirementImportance,
)


def determine_hiring_case_strength(data: HiringCaseInput) -> HiringCaseStrength:
    if data.hard_eligibility_blockers:
        return HiringCaseStrength.INELIGIBLE

    core = [item for item in data.requirements if item.importance is RequirementImportance.CORE]
    important = [
        item for item in data.requirements
        if item.importance is RequirementImportance.IMPORTANT
    ]
    if any(item.evidence_state is RequirementEvidenceState.GAP for item in core):
        return HiringCaseStrength.WEAK
    if data.seniority_context_mismatch:
        return HiringCaseStrength.WEAK
    if any(
        item.evidence_state is not RequirementEvidenceState.PROVEN for item in core
    ):
        return HiringCaseStrength.VIABLE
    if any(
        item.evidence_state in {
            RequirementEvidenceState.GAP,
            RequirementEvidenceState.EVIDENCE_MISSING,
        }
        for item in important
    ):
        return HiringCaseStrength.VIABLE
    return HiringCaseStrength.STRONG


def assess_opportunity_value(data: HiringCaseInput) -> OpportunityAssessment:
    signals = list(data.opportunity_signals)
    known = [item for item in signals if item.state is not OpportunitySignalState.UNKNOWN]
    unknown = [item for item in signals if item.state is OpportunitySignalState.UNKNOWN]
    if any(
        item.state is OpportunitySignalState.NEGATIVE
        and item.importance is RequirementImportance.CORE
        for item in signals
    ):
        value = OpportunityValue.LOW
    elif any(
        item.state is OpportunitySignalState.NEGATIVE
        and item.importance is RequirementImportance.IMPORTANT
        for item in signals
    ):
        value = OpportunityValue.MEDIUM
    elif any(item.state is OpportunitySignalState.POSITIVE for item in signals):
        value = OpportunityValue.HIGH
    else:
        value = OpportunityValue.MEDIUM

    if known and not unknown:
        confidence = OpportunityConfidence.HIGH
    elif known:
        confidence = OpportunityConfidence.MEDIUM
    else:
        confidence = OpportunityConfidence.LOW
    return OpportunityAssessment(value=value, confidence=confidence, signals=signals)


def classify_hiring_case(
    strength: HiringCaseStrength,
    opportunity_value: OpportunityValue,
) -> HiringCaseClassification:
    if strength is HiringCaseStrength.INELIGIBLE:
        return HiringCaseClassification.INELIGIBLE
    if strength is HiringCaseStrength.STRONG:
        if opportunity_value is OpportunityValue.HIGH:
            return HiringCaseClassification.BEST_MATCH
        return HiringCaseClassification.YOURE_STRONG_BUT
    if opportunity_value is OpportunityValue.HIGH:
        return HiringCaseClassification.WORTH_A_TRY
    return HiringCaseClassification.SKIP_FOR_NOW


def _proof_item(item) -> ProofItem:
    has_evidence = bool(item.evidence_refs)
    if has_evidence:
        guidance = (
            "Demonstrate the context, your actions and ownership, the methods used, "
            "and the outcome, using only the referenced experience represented in your CV."
        )
    elif item.evidence_state is RequirementEvidenceState.EVIDENCE_MISSING:
        guidance = (
            "Evidence is missing. First confirm whether you have real experience you can "
            "explain and defend; do not assume that experience exists."
        )
    else:
        guidance = "Do not claim this capability without real, defensible evidence."
    return ProofItem(
        requirement_id=item.requirement_id,
        what_they_need=item.requirement,
        evidence_we_have=list(item.evidence_refs),
        evidence_state=item.evidence_state,
        what_to_demonstrate=guidance,
        needs_evidence=item.evidence_state is RequirementEvidenceState.EVIDENCE_MISSING,
        interview_defensible=item.interview_defensible,
    )


def build_hiring_case(data: HiringCaseInput) -> HiringCase:
    strength = determine_hiring_case_strength(data)
    opportunity = assess_opportunity_value(data)
    relevant = [
        item for item in data.requirements
        if item.importance is not RequirementImportance.NICE_TO_HAVE
        or item.evidence_state in {
            RequirementEvidenceState.PROVEN,
            RequirementEvidenceState.TRANSFERABLE,
            RequirementEvidenceState.EVIDENCE_MISSING,
        }
    ]
    proof = HowToProveContract(items=[_proof_item(item) for item in relevant])
    add_evidence = [
        AddEvidenceContract(
            requirement_id=item.requirement_id,
            question=f"Do you have real experience with {item.requirement}?",
        )
        for item in data.requirements
        if item.evidence_state in {
            RequirementEvidenceState.EVIDENCE_MISSING,
            RequirementEvidenceState.GAP,
        }
    ]
    return HiringCase(
        candidate_id=data.candidate_id,
        job_id=data.job_id,
        requirements=list(data.requirements),
        hiring_case_strength=strength,
        opportunity=opportunity,
        classification=classify_hiring_case(strength, opportunity.value),
        how_to_prove=proof,
        add_evidence=add_evidence,
        hard_eligibility_blockers=list(data.hard_eligibility_blockers),
    )
