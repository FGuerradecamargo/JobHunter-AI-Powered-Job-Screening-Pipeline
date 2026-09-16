from copy import deepcopy
from dataclasses import asdict, replace
import json
import logging

import pytest

from models.candidate_priority import CandidatePriority
from models.career_objective import CareerObjective
from models.career_update import CareerUpdate
from models.hiring_case import (
    HiringCaseClassification as Classification,
    HiringCaseStrength as Strength,
    OpportunityConfidence as Confidence,
    OpportunitySignalKind as Kind,
    OpportunitySignalState as Signal,
    OpportunityValue as Value,
    RequirementEvidenceState as Evidence,
    RequirementImportance as Importance,
)
from models.hiring_case_shadow import (
    LegacyHiringClassification,
    ShadowComparisonState,
    ShadowUnavailableReason,
)
from services.application_contract_builder import build_application_evidence
from services.hiring_case_engine import build_hiring_case
from services.hiring_case_input_adapter import build_hiring_case_input
from services.hiring_case_shadow_service import (
    compare_hiring_case_fixtures,
    evaluate_hiring_case_shadow,
)
from tests.hiring_case_shadow_fixtures import comparison_fixtures, fixture_source


@pytest.mark.parametrize("index,classification,strength,proven,missing,gaps", [
    (0, Classification.BEST_MATCH, Strength.STRONG, 1, 0, 0),
    (1, Classification.YOURE_STRONG_BUT, Strength.STRONG, 1, 0, 0),
    (2, Classification.WORTH_A_TRY, Strength.WEAK, 0, 0, 1),
    (3, Classification.WORTH_A_TRY, Strength.VIABLE, 0, 1, 0),
    (4, Classification.WORTH_A_TRY, Strength.VIABLE, 0, 0, 0),
    (5, Classification.INELIGIBLE, Strength.INELIGIBLE, 1, 0, 0),
])
def test_shadow_scenarios(index, classification, strength, proven, missing, gaps):
    result = evaluate_hiring_case_shadow(comparison_fixtures()[index])
    assert result.shadow_classification is classification
    assert result.hiring_case_strength is strength
    assert result.proven_count == proven
    assert result.evidence_missing_count == missing
    assert result.needs_evidence_count == missing
    assert result.core_gap_count == gaps
    assert result.schema_version == "hiring-case-v1"
    assert result.authoritative is False


def test_existing_source_references_are_reused_without_promoting_profile_claims():
    source = fixture_source()
    source = replace(source, job_profile=replace(
        source.job_profile,
        must_have_capabilities=["Root cause analysis", "Process improvement", "SQL", "Cloud fundamentals"],
    ))
    result = build_hiring_case_input(source)
    by_label = {item.requirement: item for item in result.requirements}
    authorized = {item.evidence_ref for item in build_application_evidence(source.candidate, [])}
    assert by_label["Root cause analysis"].evidence_state is Evidence.PROVEN
    assert set(by_label["Root cause analysis"].evidence_refs) <= authorized
    for label in ["Process improvement", "SQL", "Cloud fundamentals"]:
        assert by_label[label].evidence_state is Evidence.EVIDENCE_MISSING
        assert not by_label[label].interview_defensible


def test_experience_transferable_field_is_not_promoted_by_professional_fact_authority():
    source = fixture_source()
    experience = replace(
        source.candidate.professional_experiences[0],
        demonstrated_capabilities=[], transferable_capabilities=["Root cause analysis"],
    )
    source = replace(source, candidate=replace(source.candidate, professional_experiences=[experience]))
    requirement = build_hiring_case_input(source).requirements[0]
    assert requirement.evidence_state is Evidence.TRANSFERABLE
    assert requirement.interview_defensible


def test_missing_persisted_experience_id_does_not_invent_source_backing():
    source = fixture_source()
    experience = replace(source.candidate.professional_experiences[0], source_experience_id="")
    source = replace(source, candidate=replace(source.candidate, professional_experiences=[experience]))
    assert build_hiring_case_input(source).requirements[0].evidence_state is Evidence.EVIDENCE_MISSING


def test_exact_matching_does_not_claim_broader_or_adjacent_capability():
    source = fixture_source()
    source = replace(source, job_profile=replace(source.job_profile, must_have_capabilities=[
        "Lead global root cause analysis", "Root cause analysis.",
    ]))
    states = {item.requirement: item.evidence_state for item in build_hiring_case_input(source).requirements}
    assert states["Lead global root cause analysis"] is Evidence.EVIDENCE_MISSING
    assert states["Root cause analysis."] is Evidence.PROVEN


def test_deduplication_preserves_highest_importance_and_deterministic_order():
    source = fixture_source()
    profile = replace(
        source.job_profile, must_have_experience=["Managed support escalations"],
        required_qualifications=["Degree"], structural_requirements=["License"],
        key_responsibilities=["Root cause analysis", "Reporting"],
        tools_and_technologies=["Excel"], nice_to_have=["Reporting", "Python"],
    )
    source = replace(source, job_profile=profile)
    first = build_hiring_case_input(source)
    importance = {item.requirement: item.importance for item in first.requirements}
    assert importance == {
        "Root cause analysis": Importance.CORE, "Managed support escalations": Importance.CORE,
        "Degree": Importance.CORE, "License": Importance.CORE,
        "Reporting": Importance.IMPORTANT, "Excel": Importance.IMPORTANT, "Python": Importance.NICE_TO_HAVE,
    }
    reversed_source = replace(source, job_profile=replace(
        profile, key_responsibilities=list(reversed(profile.key_responsibilities)),
        nice_to_have=list(reversed(profile.nice_to_have)),
    ))
    assert build_hiring_case_input(reversed_source) == first


def test_missing_evidence_never_becomes_gap_from_legacy_inference_or_learning_goals():
    source = comparison_fixtures()[3]
    source = replace(
        source, candidate=replace(source.candidate, development_areas=["SQL"]),
        analysis_source=replace(source.analysis_source, analysis={
            "structural_gaps": ["SQL"], "development_gaps": ["SQL"],
            "requirements_met": ["SQL"], "strengths": ["SQL"],
            "current_fit": 100, "growth_value": 100,
        }),
    )
    result = evaluate_hiring_case_shadow(source)
    assert result.gap_count == 0
    assert result.proven_count == 0
    assert result.evidence_missing_count == 1


def test_confirmed_gap_requires_existing_source_reference():
    source = comparison_fixtures()[2]
    with pytest.raises(ValueError, match="existing source"):
        build_hiring_case_input(replace(source, career_updates=()))


def test_conflicting_gap_and_proof_require_review_instead_of_selecting_convenient_fact():
    source = comparison_fixtures()[2]
    experience = replace(source.candidate.professional_experiences[0], demonstrated_capabilities=["Cloud operations"])
    source = replace(source, candidate=replace(source.candidate, professional_experiences=[experience]))
    item = build_hiring_case_input(source).requirements[0]
    assert item.evidence_state is Evidence.EVIDENCE_MISSING
    assert "conflicts" in item.rationale
    assert not item.interview_defensible


@pytest.mark.parametrize("salary", [None, "", "Negotiable", "EUR 65,000 yearly", "USD 70/hour"])
def test_salary_without_comparable_currency_period_remains_unknown(salary):
    source = fixture_source()
    source = replace(source, analysis_source=replace(
        source.analysis_source, job={**source.analysis_source.job, "salary": salary},
    ))
    data = build_hiring_case_input(source)
    compensation = next(item for item in data.opportunity_signals if item.kind is Kind.COMPENSATION)
    assert compensation.state is Signal.UNKNOWN
    result = evaluate_hiring_case_shadow(source)
    assert result.opportunity_value is Value.HIGH
    assert result.opportunity_confidence is Confidence.MEDIUM


def test_known_preferences_and_missing_opportunity_dimensions():
    source = fixture_source()
    source = replace(source, job_profile=replace(source.job_profile, work_conditions=["onsite"]))
    data = build_hiring_case_input(source)
    signals = {item.kind: item.state for item in data.opportunity_signals}
    assert set(signals) == set(Kind)
    assert signals[Kind.WORK_MODE_LOCATION] is Signal.NEGATIVE
    assert signals[Kind.STRATEGIC_VALUE] is Signal.UNKNOWN
    assert signals[Kind.OBJECTIVE_TIMING] is Signal.UNKNOWN
    assert signals[Kind.SENIORITY_PROGRESSION] is Signal.UNKNOWN


def test_remote_false_does_not_infer_onsite_and_permission_does_not_invent_value():
    source = fixture_source()
    source = replace(source, candidate=replace(source.candidate, target_role_families=[]))
    for remote in [False, None, True]:
        current = replace(source, analysis_source=replace(
            source.analysis_source, job={**source.analysis_source.job, "remote": remote},
        ))
        result = evaluate_hiring_case_shadow(current)
        assert result.opportunity_value is Value.MEDIUM
        assert result.opportunity_confidence is Confidence.LOW


def test_active_objective_takes_precedence_and_nonmatching_family_is_unknown():
    source = fixture_source()
    objective = CareerObjective("objective", source.candidate.id, "Private", "Private", desired_role_families=["Finance"])
    source = replace(source, objective=objective)
    result = evaluate_hiring_case_shadow(source)
    assert result.opportunity_value is Value.MEDIUM
    assert result.opportunity_confidence is Confidence.LOW
    inactive = replace(source, objective=replace(objective, active=False))
    assert evaluate_hiring_case_shadow(inactive).opportunity_value is Value.HIGH


def test_requirements_fallback_uses_job_facts_but_not_requirements_met():
    source = fixture_source()
    source = replace(source, job_profile=None, analysis_source=replace(
        source.analysis_source, analysis={"core_requirements": ["Root cause analysis"], "requirements_met": ["Imaginary skill"]},
    ))
    data = build_hiring_case_input(source)
    assert len(data.requirements) == 1
    assert data.requirements[0].evidence_state is Evidence.PROVEN


@pytest.mark.parametrize("profile_missing", [True, False])
def test_missing_core_information_abstains_instead_of_vacuous_strong_case(profile_missing):
    source = fixture_source()
    profile = None if profile_missing else replace(source.job_profile, must_have_capabilities=[], nice_to_have=["SQL"])
    result = evaluate_hiring_case_shadow(replace(source, job_profile=profile))
    assert result.comparison is ShadowComparisonState.NOT_EVALUATED
    assert result.shadow_classification is None
    assert result.unavailable_reason is ShadowUnavailableReason.CORE_REQUIREMENTS_MISSING


def test_no_analysis_cannot_start_shadow_generation():
    source = fixture_source()
    result = evaluate_hiring_case_shadow(replace(
        source, analysis_source=replace(source.analysis_source, analysis_id=""),
    ))
    assert result.unavailable_reason is ShadowUnavailableReason.ANALYSIS_MISSING


def test_hard_filter_remains_ineligible_even_without_requirements():
    source = comparison_fixtures()[5]
    result = evaluate_hiring_case_shadow(replace(source, job_profile=None))
    assert result.shadow_classification is Classification.INELIGIBLE


@pytest.mark.parametrize("scope", ["candidate", "job", "profile", "objective", "update", "gap"])
def test_cross_scope_inputs_are_rejected(scope):
    source = comparison_fixtures()[2]
    changes = {
        "candidate": {"candidate": replace(source.candidate, id="other")},
        "job": {"analysis_source": replace(source.analysis_source, job={"id": "other"})},
        "profile": {"job_profile": replace(source.job_profile, job_id="other")},
        "objective": {"objective": CareerObjective("o", "other", "", "")},
        "update": {"career_updates": (replace(source.career_updates[0], candidate_id="other"),)},
        "gap": {"confirmed_gaps": (replace(source.confirmed_gaps[0], candidate_id="other"),)},
    }
    with pytest.raises(PermissionError):
        evaluate_hiring_case_shadow(replace(source, **changes[scope]))


def test_legacy_analysis_without_metadata_is_unchanged_and_needs_no_database(monkeypatch):
    from services import database
    def forbidden(*args, **kwargs):
        raise AssertionError("No persistence is allowed in shadow computation.")
    monkeypatch.setattr(database, "get_connection", forbidden)
    source = fixture_source()
    source.analysis_source.analysis["bucket"] = "potential"
    before = deepcopy(source)
    result = evaluate_hiring_case_shadow(source)
    assert result.legacy_value is LegacyHiringClassification.POTENTIAL
    assert result.comparison is ShadowComparisonState.DIFFERENT
    assert source == before
    assert "shadow" not in source.analysis_source.analysis


def test_comparison_maps_legacy_labels_before_comparing():
    missing = comparison_fixtures()[3]
    result = evaluate_hiring_case_shadow(missing)
    assert result.legacy_value is LegacyHiringClassification.POTENTIAL
    assert result.shadow_classification is Classification.WORTH_A_TRY
    assert result.comparison is ShadowComparisonState.SAME


def test_diagnostics_and_comparison_never_contain_private_content(caplog):
    caplog.set_level(logging.INFO, logger="services.hiring_case_shadow_service")
    source = fixture_source()
    secret = "PRIVATE-CV-EMAIL-NOTES-SENTINEL"
    experience = replace(source.candidate.professional_experiences[0], demonstrated_capabilities=[secret])
    source = replace(
        source, candidate=replace(source.candidate, name=secret, professional_summary=secret, professional_experiences=[experience]),
        job_profile=replace(source.job_profile, must_have_capabilities=[secret]),
        analysis_source=replace(source.analysis_source, recommendation=secret, analysis={"private_notes": secret}),
    )
    result = evaluate_hiring_case_shadow(source)
    payload = json.dumps(asdict(result))
    assert secret not in payload + caplog.text
    assert source.candidate.id not in payload + caplog.text
    assert result.legacy_value is LegacyHiringClassification.UNKNOWN
    assert result.comparison is ShadowComparisonState.UNMAPPED
    event = json.loads(caplog.records[-1].message)
    assert event["event"] == "hiring_case_shadow"
    assert event["proven_count"] == 1
    assert event["authoritative"] is False


def test_local_comparison_harness_is_deterministic_and_content_free():
    sources = comparison_fixtures()
    result = compare_hiring_case_fixtures(sources)
    assert result == compare_hiring_case_fixtures(reversed(sources))
    assert result["total"] == 8
    assert result["same"] == 3
    assert result["changed"] == 4
    assert result["unmapped"] == 1
    assert result["evidence_missing_total"] == 1
    assert result["core_gap_total"] == 1
    assert result["evidence_missing_average"] == 0.125
    assert result["core_gap_average"] == 0.125
    assert result["transitions"]["potential -> best_match"] == 1
    assert result["transitions"]["best_match -> youre_strong_but"] == 1
    assert result["transitions"]["good_opportunity -> best_match"] == 1
    assert result["transitions"]["competitive -> worth_a_try"] == 1


def test_empty_and_unevaluable_fixture_reports_do_not_divide_by_zero():
    assert compare_hiring_case_fixtures([])["total"] == 0
    source = fixture_source()
    result = compare_hiring_case_fixtures([replace(source, job_profile=None)])
    assert result["total"] == 1
    assert result["not_evaluated"] == 1
    assert result["evaluated"] == 0
    assert result["evidence_missing_average"] == 0.0
