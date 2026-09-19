from dataclasses import asdict, replace
import json
import socket

import pytest

from models.hiring_case import (
    EvidenceRequirement as Requirement, EvidenceConstraintReason, HiringCaseInput,
    RequirementAssessment, RequirementEvidenceState as Evidence, RequirementImportance as Importance,
)
from models.profile_interpretation import InterpretationAuthority as Authority
from models.structured_interpretation import (
    InterpretationOperation as Op, ValidationIssue as Issue, ValidationStatus as Status,
    RegisteredSourceRef, SourceRefClass as Ref,
)
from services.hiring_case_engine import build_hiring_case
from services.profile_hiring_case_adapter import build_profile_hiring_case_input
from services.profile_snapshot_repository import _job_from_json
from tests.test_offline_structured_interpreter import request, run, opportunity_req, signal
from tests.hiring_case_adversarial_cases import adversarial_cases
from tests.hiring_case_adversarial_runner import observe


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External IO forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    from services import database
    monkeypatch.setattr(database, "get_connection", forbidden)


def assessment(importance=Importance.IMPORTANT, state=Evidence.TRANSFERABLE, requirement=Requirement.DIRECT_REQUIRED):
    return RequirementAssessment("target", "Release ownership", importance, state,
                                 ["evidence"] if state in {Evidence.PROVEN, Evidence.TRANSFERABLE} else [],
                                 interview_defensible=state in {Evidence.PROVEN, Evidence.TRANSFERABLE},
                                 evidence_requirement=requirement)


def case_for(item):
    core = RequirementAssessment("core", "Incident recovery", Importance.CORE, Evidence.PROVEN, ["core-ref"])
    return build_hiring_case(HiringCaseInput("candidate", "job", [core, item]))


@pytest.mark.parametrize("importance,requirement,strength", [
    (Importance.IMPORTANT, Requirement.DEFENSIBLE, "strong"),
    (Importance.IMPORTANT, Requirement.DIRECT_REQUIRED, "viable"),
    (Importance.CORE, Requirement.DIRECT_REQUIRED, "weak"),
    (Importance.NICE_TO_HAVE, Requirement.DIRECT_REQUIRED, "strong"),
])
def test_importance_and_evidence_requirement_are_orthogonal(importance, requirement, strength):
    item = assessment(importance, requirement=requirement)
    result = case_for(item)
    assert result.hiring_case_strength.value == strength
    assert item.evidence_state is Evidence.TRANSFERABLE
    assert item.constraint_satisfied is (requirement is Requirement.DEFENSIBLE)
    assert result.hiring_case_strength.value != "ineligible"
    assert not result.add_evidence


@pytest.mark.parametrize("state,satisfied", [(Evidence.PROVEN, True), (Evidence.TRANSFERABLE, False),
                                            (Evidence.EVIDENCE_MISSING, False), (Evidence.GAP, False)])
def test_constraint_result_cannot_mutate_capability_truth(state, satisfied):
    item = assessment(state=state)
    result = case_for(item)
    assert item.constraint_satisfied is satisfied
    assert result.requirements[-1].evidence_state is state
    assert bool(result.add_evidence) is (state is Evidence.EVIDENCE_MISSING)
    if not satisfied:
        assert item.constraint_reason_code is EvidenceConstraintReason.DIRECT_EVIDENCE_REQUIRED


def test_how_to_prove_keeps_adjacent_scope_and_does_not_request_fake_evidence():
    result = case_for(assessment())
    item = result.how_to_prove.items[-1]
    assert item.evidence_state is Evidence.TRANSFERABLE
    assert not item.constraint_satisfied and not item.needs_evidence
    assert item.evidence_requirement is Requirement.DIRECT_REQUIRED
    assert "not established" in item.what_to_demonstrate
    assert "do not present it as direct ownership" in item.what_to_demonstrate
    assert not result.add_evidence


@pytest.mark.parametrize("importance", list(Importance))
def test_proven_direct_evidence_satisfies_each_importance(importance):
    item = assessment(importance, Evidence.PROVEN)
    assert item.constraint_satisfied
    assert case_for(item).hiring_case_strength.value == "strong"


def job_request(*, source_required=True):
    req = request(Op.BUILD_JOB_PROFILE)
    hard = replace(req.hard_facts, facts=(replace(req.hard_facts.facts[0],
        evidence_requirement=Requirement.DIRECT_REQUIRED if source_required else Requirement.DEFENSIBLE,
        constraint_need_id="need-1" if source_required else ""),))
    return replace(req, hard_facts=hard, job_profile=None)


def job_reply(**changes):
    need = dict(need_id="need-1", label="Own releases", importance="important", authority="explicit",
                hard_fact_refs=["f1"], evidence_requirement="direct_required", evidence_requirement_refs=["f1"])
    need.update(changes)
    return {"needs": [need]}


@pytest.mark.parametrize("authority", ["strongly_implied", "unknown"])
def test_inferred_direct_requirement_rejected_even_with_real_refs(authority):
    result = run(job_request(), job_reply(authority=authority))
    assert result.validation_status is Status.REJECTED
    assert result.validation_issue_codes == (Issue.UNSUPPORTED_DIRECT_EVIDENCE_REQUIREMENT,)


@pytest.mark.parametrize("refs", [["invented"], ["checkpoint:v1"], ["experience:1"]])
def test_direct_requirement_cannot_cite_invalid_candidate_or_checkpoint_ref(refs):
    assert run(job_request(), job_reply(evidence_requirement_refs=refs)).validation_status is Status.REJECTED


def test_future_ownership_does_not_create_prior_ownership_requirement():
    assert run(job_request(source_required=False), job_reply()).validation_issue_codes == (Issue.UNSUPPORTED_DIRECT_EVIDENCE_REQUIREMENT,)


def test_interpreter_cannot_drop_explicit_hard_constraint():
    assert run(job_request(), job_reply(evidence_requirement="defensible", evidence_requirement_refs=[])).validation_status is Status.REJECTED


def test_constraint_ref_is_bound_to_the_need_not_merely_valid():
    req = job_request()
    req = replace(req, hard_facts=replace(req.hard_facts,
                  facts=(replace(req.hard_facts.facts[0], constraint_need_id="other-need"),)))
    assert run(req, job_reply()).validation_status is Status.REJECTED


def test_valid_constraint_and_legacy_snapshot_decoding():
    req = job_request()
    result = run(req, job_reply())
    assert result.validation_status is Status.ACCEPTED
    original = request().job_profile
    profile = replace(original, needs=result.output_payload.needs)
    assert _job_from_json(json.dumps(asdict(profile))) == profile
    old = asdict(original)
    for need in old["needs"]:
        need.pop("evidence_requirement")
        need.pop("evidence_requirement_refs")
    decoded = _job_from_json(json.dumps(old))
    assert decoded.needs[0].evidence_requirement is Requirement.DEFENSIBLE


def test_profile_adapter_also_blocks_unvalidated_constraint():
    from models.profile_interpretation import HiringCaseInterpretation
    req = request()
    need = replace(req.job_profile.needs[0], evidence_requirement=Requirement.DIRECT_REQUIRED,
                   evidence_requirement_refs=("f1",))
    with pytest.raises(ValueError, match="unsupported_direct_evidence_requirement"):
        build_profile_hiring_case_input(candidate_profile=req.candidate_profile,
            job_profile=replace(req.job_profile, needs=(need,)), hard_facts=req.hard_facts,
            interpretation=HiringCaseInterpretation(()))


def conflicting_request():
    req = opportunity_req(True)
    refs = ("preference:a", "preference:b")
    registry = req.source_registry + tuple(RegisteredSourceRef(ref, Ref.CAREER_MEMORY_SOURCE,
                    req.candidate_id, "candidate_preference") for ref in refs)
    fact = replace(req.opportunity_facts[0], supporting_refs=refs, facts=("Prefer A", "Avoid A"),
                   conflicting_preference_refs=refs)
    return replace(req, source_registry=registry, opportunity_facts=(fact,))


@pytest.mark.parametrize("valence", ["positive", "negative", "unknown"])
def test_equal_current_preferences_never_choose_a_valence(valence):
    req = conflicting_request()
    result = run(req, signal(state=valence, supporting_refs=["preference:a", "preference:b"]))
    assert Issue.CONFLICTING_PREFERENCES in result.validation_issue_codes
    assert all(item.state.value == "unknown" for item in result.output_payload.signals)
    assert "conflict" in result.output_payload.signals[0].uncertainty or any("conflict" in item.uncertainty for item in result.output_payload.signals)


@pytest.mark.parametrize("refs", [("preference:a",), ("preference:a", "preference:a"),
                                   ("checkpoint:v1", "preference:a"), ("f1", "preference:a")])
def test_conflicts_require_two_distinct_candidate_preference_sources(refs):
    req = conflicting_request()
    fact = replace(req.opportunity_facts[0], supporting_refs=refs, conflicting_preference_refs=refs)
    assert run(replace(req, opportunity_facts=(fact,)), signal(supporting_refs=list(refs))).validation_status is Status.REJECTED


def test_removing_resolved_conflict_requires_new_input_signature():
    from services.fixture_structured_interpreter import fixture_key, FixtureStructuredInterpreter
    req = conflicting_request()
    interpreter = FixtureStructuredInterpreter({fixture_key(req): signal(supporting_refs=["preference:a", "preference:b"])})
    resolved = replace(req, opportunity_facts=(replace(req.opportunity_facts[0], conflicting_preference_refs=()),))
    assert interpreter.interpret(resolved).validation_status is Status.UNAVAILABLE
    assert run(resolved, signal(state="positive", supporting_refs=["preference:a", "preference:b"])).output_payload.signals[0].state.value == "positive"


def test_av02_and_av30_resolved_but_semantic_failures_visible():
    rows = {case.case_id: observe(case) for case in adversarial_cases()}
    assert rows["AV02"]["classification"] == "worth_a_try"
    assert rows["AV02"]["states"] == ("proven", "evidence_missing")
    assert rows["AV02"]["constraints"][1] == ("direct_required", False, "direct_evidence_required")
    assert rows["AV30"]["value"] == "medium" and rows["AV30"]["confidence"] == "low"
    for case in ("AV05", "AV06", "AV27"):
        assert rows[case]["classification"] == "best_match"
