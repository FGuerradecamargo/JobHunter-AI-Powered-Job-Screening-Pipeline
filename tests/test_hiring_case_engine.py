import pytest

from models.hiring_case import (
    EVIDENCE_WARNING,
    AddEvidenceContract,
    ExperienceAnswer,
    HiringCaseClassification,
    HiringCaseInput,
    HiringCaseStrength,
    OpportunityConfidence,
    OpportunitySignal,
    OpportunitySignalKind,
    OpportunitySignalState,
    OpportunityValue,
    RequirementAssessment,
    RequirementEvidenceState,
    RequirementImportance,
    StructuredEvidenceDraft,
)
from services.hiring_case_compatibility import read_legacy_classification
from services.hiring_case_engine import build_hiring_case


def requirement(
    state=RequirementEvidenceState.PROVEN,
    *,
    importance=RequirementImportance.CORE,
    identity="fraud",
    evidence=True,
):
    refs = [f"e-{identity}"] if evidence else []
    return RequirementAssessment(
        requirement_id=identity,
        requirement="Fraud investigation",
        importance=importance,
        evidence_state=state,
        evidence_refs=refs,
        rationale="Grounded support for this requirement.",
        interview_defensible=bool(refs),
    )


def signal(
    state=OpportunitySignalState.POSITIVE,
    *,
    kind=OpportunitySignalKind.CAREER_DIRECTION,
    importance=RequirementImportance.CORE,
):
    return OpportunitySignal(
        kind=kind,
        state=state,
        importance=importance,
        rationale="Candidate-specific value signal.",
    )


def case(*requirements, signals=None, blockers=None, seniority_mismatch=False):
    return build_hiring_case(
        HiringCaseInput(
            candidate_id="candidate-a",
            job_id="job-1",
            requirements=list(requirements),
            opportunity_signals=list(signals or []),
            hard_eligibility_blockers=list(blockers or []),
            seniority_context_mismatch=seniority_mismatch,
        )
    )


@pytest.mark.parametrize(
    "requirements,signals,expected_strength,expected_value,expected_classification",
    [
        # A: direct proof plus high candidate value.
        ([requirement()], [signal()], HiringCaseStrength.STRONG, OpportunityValue.HIGH, HiringCaseClassification.BEST_MATCH),
        # B: growth value cannot hide a material core gap.
        ([requirement(RequirementEvidenceState.GAP, evidence=False)], [signal()], HiringCaseStrength.WEAK, OpportunityValue.HIGH, HiringCaseClassification.WORTH_A_TRY),
        # C: a strong company case remains distinct from low candidate value.
        ([requirement()], [signal(OpportunitySignalState.NEGATIVE)], HiringCaseStrength.STRONG, OpportunityValue.LOW, HiringCaseClassification.YOURE_STRONG_BUT),
        # D: neither dimension justifies attention.
        ([requirement(RequirementEvidenceState.GAP, evidence=False)], [signal(OpportunitySignalState.NEGATIVE)], HiringCaseStrength.WEAK, OpportunityValue.LOW, HiringCaseClassification.SKIP_FOR_NOW),
        # F: transferable core evidence is viable, never direct proof.
        ([requirement(RequirementEvidenceState.TRANSFERABLE)], [signal()], HiringCaseStrength.VIABLE, OpportunityValue.HIGH, HiringCaseClassification.WORTH_A_TRY),
        # G: nice-to-have gaps do not destroy an otherwise strong case.
        ([requirement(), requirement(RequirementEvidenceState.GAP, importance=RequirementImportance.NICE_TO_HAVE, identity="nice", evidence=False)], [signal()], HiringCaseStrength.STRONG, OpportunityValue.HIGH, HiringCaseClassification.BEST_MATCH),
    ],
)
def test_two_dimension_classification_table(
    requirements, signals, expected_strength, expected_value, expected_classification
):
    result = case(*requirements, signals=signals)
    assert result.hiring_case_strength is expected_strength
    assert result.opportunity.value is expected_value
    assert result.classification is expected_classification


def test_evidence_missing_is_not_gap_and_exposes_evidence_need():
    result = case(
        requirement(RequirementEvidenceState.EVIDENCE_MISSING, evidence=False),
        signals=[signal()],
    )
    assert result.hiring_case_strength is HiringCaseStrength.VIABLE
    assert result.requirements[0].evidence_state is RequirementEvidenceState.EVIDENCE_MISSING
    assert result.how_to_prove.items[0].needs_evidence is True
    assert result.how_to_prove.items[0].evidence_we_have == []
    assert "do not assume" in result.how_to_prove.items[0].what_to_demonstrate


def test_hard_blocker_is_upstream_and_cannot_be_promoted():
    result = case(requirement(), signals=[signal()], blockers=["work authorization"])
    assert result.hiring_case_strength is HiringCaseStrength.INELIGIBLE
    assert result.opportunity.value is OpportunityValue.HIGH
    assert result.classification is HiringCaseClassification.INELIGIBLE


def test_seniority_context_mismatch_materially_weakens_case():
    result = case(requirement(), signals=[signal()], seniority_mismatch=True)
    assert result.hiring_case_strength is HiringCaseStrength.WEAK
    assert result.classification is HiringCaseClassification.WORTH_A_TRY


def test_missing_salary_is_uncertainty_not_negative_value():
    result = case(
        requirement(),
        signals=[
            signal(),
            signal(
                OpportunitySignalState.UNKNOWN,
                kind=OpportunitySignalKind.COMPENSATION,
                importance=RequirementImportance.CORE,
            ),
        ],
    )
    assert result.opportunity.value is OpportunityValue.HIGH
    assert result.opportunity.confidence is OpportunityConfidence.MEDIUM
    assert result.classification is HiringCaseClassification.BEST_MATCH


def test_only_unknown_opportunity_information_is_medium_with_low_confidence():
    result = case(
        requirement(),
        signals=[signal(OpportunitySignalState.UNKNOWN)],
    )
    assert result.opportunity.value is OpportunityValue.MEDIUM
    assert result.opportunity.confidence is OpportunityConfidence.LOW


def test_how_to_prove_is_grounded_and_not_a_scripted_answer():
    result = case(requirement(), signals=[signal()])
    item = result.how_to_prove.items[0]
    assert item.evidence_we_have == ["e-fraud"]
    assert item.interview_defensible is True
    assert "context, your actions and ownership" in item.what_to_demonstrate
    assert "I " not in item.what_to_demonstrate
    assert "e-fraud" not in item.what_to_demonstrate


@pytest.mark.parametrize(
    "state,evidence,defensible",
    [
        (RequirementEvidenceState.PROVEN, False, False),
        (RequirementEvidenceState.TRANSFERABLE, False, False),
        (RequirementEvidenceState.EVIDENCE_MISSING, False, True),
        (RequirementEvidenceState.GAP, False, True),
    ],
)
def test_requirement_contract_rejects_unsupported_authority(
    state, evidence, defensible
):
    with pytest.raises(ValueError):
        RequirementAssessment(
            requirement_id="fraud",
            requirement="Fraud investigation",
            importance=RequirementImportance.CORE,
            evidence_state=state,
            evidence_refs=["e-fraud"] if evidence else [],
            interview_defensible=defensible,
        )


def test_requirement_rationale_is_short_normalized_and_refs_are_deterministic():
    item = RequirementAssessment(
        requirement_id="  fraud  ",
        requirement="  Fraud\n investigation ",
        importance=RequirementImportance.CORE,
        evidence_state=RequirementEvidenceState.PROVEN,
        evidence_refs=["e-two", " e-one ", "e-two"],
        rationale="  short\n sanitized   rationale  ",
        interview_defensible=True,
    )
    assert item.requirement == "Fraud investigation"
    assert item.rationale == "short sanitized rationale"
    assert item.evidence_refs == ["e-one", "e-two"]


def test_add_evidence_contract_is_two_stage_and_requires_truth_warning():
    result = case(
        requirement(RequirementEvidenceState.EVIDENCE_MISSING, evidence=False),
        signals=[signal()],
    )
    contract = result.add_evidence[0]
    assert contract.answer is None
    assert contract.structured_evidence is None
    assert contract.confirmation_required is True
    assert contract.warning == EVIDENCE_WARNING
    no_answer = AddEvidenceContract(
        requirement_id="fraud", question=contract.question, answer=ExperienceAnswer.NO
    )
    assert no_answer.structured_evidence is None


def test_yes_evidence_requires_acknowledgement_and_structured_fields():
    draft = StructuredEvidenceDraft(
        context="Payment review",
        candidate_action="Investigated evidence and owned the decision",
        tools_or_methods="Case management and transaction data",
        result_or_impact="Escalated the confirmed risk",
        timeframe_or_source="Prior role",
        warning_acknowledged=False,
    )
    with pytest.raises(ValueError, match="warning"):
        AddEvidenceContract(
            requirement_id="fraud",
            question="Do you have real experience with fraud investigation?",
            answer=ExperienceAnswer.YES,
            structured_evidence=draft,
        )


@pytest.mark.parametrize(
    "legacy,expected",
    [
        ("best_match", HiringCaseClassification.BEST_MATCH),
        ("potential", HiringCaseClassification.WORTH_A_TRY),
        ("good_opportunity", HiringCaseClassification.YOURE_STRONG_BUT),
        ("competitive", HiringCaseClassification.YOURE_STRONG_BUT),
        ("unknown_future_value", None),
    ],
)
def test_legacy_read_compatibility_is_explicit_and_not_reinterpreted(legacy, expected):
    view = read_legacy_classification(legacy)
    assert view.display_classification is expected
    assert view.original_recommendation == legacy
    assert view.source_schema_version == "legacy-analysis"
    assert view.produced_by_hiring_case_engine is False
