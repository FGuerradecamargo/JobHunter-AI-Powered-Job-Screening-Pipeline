from dataclasses import replace
import pytest

from models.hiring_case import (
    HiringCaseClassification as Classification, HiringCaseStrength as Strength,
    RequirementEvidenceState as Evidence, RequirementImportance as Importance,
)
from tests.test_hiring_case_engine import case, requirement, signal
from models.hiring_case import OpportunitySignalState, OpportunityConfidence


@pytest.mark.parametrize("requirements", [
    [],
    [requirement(Evidence.EVIDENCE_MISSING, evidence=False)],
    [requirement(importance=Importance.NICE_TO_HAVE)],
    [requirement(Evidence.EVIDENCE_MISSING, evidence=False, importance=Importance.IMPORTANT)],
])
def test_no_relevant_evaluation_never_surfaces(requirements):
    result = case(*requirements, signals=[signal()])
    assert result.classification is Classification.NOT_SURFACED
    assert result.surfacing_reason == "insufficient_evidence"
    assert result.evaluated_requirement_count == 0
    assert result.hiring_case_strength is Strength.UNKNOWN
    assert not result.surfaced
    assert not result.hard_eligibility_blockers
    assert result.requirements == requirements


def test_partial_positive_support_and_candidate_value_can_surface():
    result = case(requirement(Evidence.TRANSFERABLE),
                  requirement(Evidence.EVIDENCE_MISSING, evidence=False, identity="unknown"),
                  signals=[signal(), signal(OpportunitySignalState.UNKNOWN)])
    assert result.classification is Classification.WORTH_A_TRY
    assert result.surfaced
    assert result.positive_requirement_count == 1
    assert result.opportunity.confidence is OpportunityConfidence.MEDIUM
    assert result.add_evidence


def test_unsupported_proven_claim_is_rejected_before_classification():
    with pytest.raises(ValueError, match="evidence refs"):
        requirement(Evidence.PROVEN, evidence=False)


def test_negative_evaluation_alone_cannot_become_positive_recommendation():
    gap = replace(requirement(Evidence.GAP, evidence=False), evidence_refs=["confirmed-absence"])
    result = case(gap, signals=[signal()])
    assert result.evaluated_requirement_count == 1
    assert result.positive_requirement_count == 0
    assert result.classification is Classification.NOT_SURFACED
    assert result.surfacing_reason == "no_grounded_positive_support"


def test_strong_grounded_fit_with_poor_candidate_value():
    result = case(requirement(), signals=[signal(OpportunitySignalState.NEGATIVE)])
    assert result.classification is Classification.YOURE_STRONG_BUT
    assert result.hiring_case_strength is Strength.STRONG


def test_transferable_important_support_alone_does_not_establish_strength():
    result = case(requirement(Evidence.TRANSFERABLE, importance=Importance.IMPORTANT),
                  signals=[signal(OpportunitySignalState.NEGATIVE)])
    assert result.hiring_case_strength is Strength.VIABLE
    assert result.classification is not Classification.YOURE_STRONG_BUT


def test_best_match_requires_support_on_both_dimensions():
    result = case(requirement(), signals=[signal()])
    assert result.classification is Classification.BEST_MATCH
    assert case(requirement(), signals=[]).classification is not Classification.BEST_MATCH
    assert not case(signals=[signal()]).surfaced


@pytest.mark.parametrize("requirements", [[], [requirement(Evidence.EVIDENCE_MISSING, evidence=False)], [requirement()]])
def test_authoritative_hard_blocker_wins(requirements):
    result = case(*requirements, signals=[signal()], blockers=["Confirmed incompatibility"])
    assert result.classification is Classification.INELIGIBLE
    assert result.surfacing_reason == "hard_incompatibility"
    assert not result.surfaced


def test_official_profile_service_cannot_promote_an_empty_job_profile():
    from models.profile_interpretation import HiringCaseInterpretation
    from services.authoritative_hiring_case_service import AuthoritativeHiringCaseService
    from tests.test_workpilot_v1_authoritative_hiring_case import candidate, job

    profile, hard_facts = job()
    class EmptyInterpreter:
        def analyze_hiring_case(self, **kwargs):
            return HiringCaseInterpretation(requirement_links=(), opportunity_signals=(signal(),))
    result = AuthoritativeHiringCaseService(EmptyInterpreter()).evaluate(
        candidate_profile=candidate(), job_profile=replace(profile, needs=()), hard_facts=hard_facts,
    )
    assert result.classification is Classification.NOT_SURFACED
    assert result.surfacing_reason == "insufficient_evidence"
    assert result.candidate_profile_version == 3
    assert result.job_profile_version == 2
