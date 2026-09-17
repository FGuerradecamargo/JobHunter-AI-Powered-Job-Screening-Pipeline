from copy import deepcopy
from dataclasses import asdict, replace
import json
import logging
import socket

import pytest

from models.hiring_case import OpportunitySignalKind as Kind, RequirementEvidenceState as Evidence
from models.profile_interpretation import ProfileCheckpoint
from models.structured_interpretation import (
    FactState, InterpretationOperation as Op, OpportunityFact, RegisteredSourceRef,
    SourceRefClass as Ref, StructuredInterpretationInput as Request,
    ValidationIssue as Issue, ValidationStatus as Status,
)
from services.fixture_structured_interpreter import FixtureStructuredInterpreter, fixture_key, input_signature
from services.structured_profile_boundary import accepted_payload, candidate_snapshot, hiring_interpretation
from services.structured_interpretation_validation import InterpretationValidationError
from tests.test_profile_interpretation_architecture import profiles


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External IO forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    from services import database
    monkeypatch.setattr(database, "get_connection", forbidden)


def request(operation=Op.ANALYZE_HIRING_CASE):
    candidate, job, hard = profiles()
    registry = (
        RegisteredSourceRef("experience:1", Ref.CANDIDATE_EVIDENCE, candidate.candidate_id, "professional_experience", True),
        RegisteredSourceRef("memory:context", Ref.CAREER_MEMORY_SOURCE, candidate.candidate_id, "candidate_context"),
        RegisteredSourceRef("f1", Ref.JOB_HARD_FACT, job.job_id, "job_description"),
        RegisteredSourceRef("checkpoint:v1", Ref.DERIVED_CHECKPOINT, candidate.candidate_id, "checkpoint"),
    )
    return Request(operation, candidate.candidate_id, job.job_id,
                   memory_signature="fixture-source-v1", memory_projection={"source": "fixture"},
                   source_registry=registry, candidate_profile=candidate, job_profile=job, hard_facts=hard)


def link(**changes):
    raw = dict(need_id="need-1", candidate_capability_id="cap", assessment="proven",
               evidence_refs=["experience:1"], confidence="high", reason_code="direct_support", needs_evidence=False)
    raw.update(changes)
    return {"links": [raw]}


def run(req, raw):
    return FixtureStructuredInterpreter({fixture_key(req): raw}, clock=lambda: "2026-01-01T00:00:00+00:00").interpret(req)


def test_missing_fixture_abstains_and_changed_input_cannot_reuse_old_response():
    req = request()
    interpreter = FixtureStructuredInterpreter({fixture_key(req): link()})
    assert interpreter.interpret(req).validation_status is Status.ACCEPTED
    for changed in (
        replace(req, candidate_id="other"),
        replace(req, candidate_profile=replace(req.candidate_profile, profile_version=2)),
        replace(req, job_profile=replace(req.job_profile, job_signature="changed")),
        replace(req, operation=Op.BUILD_JOB_PROFILE),
    ):
        result = interpreter.interpret(changed)
        assert result.validation_status is Status.UNAVAILABLE
        assert result.output_payload is None


@pytest.mark.parametrize("state", ["proven", "transferable"])
def test_missing_proof_normalizes_and_question_hint_cannot_promote(state):
    req = request()
    result = run(req, link(assessment=state, evidence_refs=[], evidence_question_hint="I definitely did this PRIVATE"))
    assert result.validation_status is Status.NORMALIZED
    item = result.output_payload.links[0]
    assert item.assessment is Evidence.EVIDENCE_MISSING
    assert item.needs_evidence and not item.evidence_refs
    assert "PRIVATE" in item.evidence_question_hint


@pytest.mark.parametrize("ref,code", [
    ("checkpoint:v1", Issue.CHECKPOINT_AS_EVIDENCE),
    ("unknown-ref", Issue.UNKNOWN_REF),
    ("f1", Issue.WRONG_SOURCE_CLASS),
    ("memory:context", Issue.WRONG_SOURCE_CLASS),
])
def test_evidence_ref_firewall(ref, code):
    result = run(request(), link(evidence_refs=[ref]))
    assert result.validation_status is Status.REJECTED
    assert result.validation_issue_codes == (code,)
    assert result.output_payload is None


def test_checkpoint_cannot_be_laundered_by_registering_it_as_candidate_evidence():
    req = request()
    forged = RegisteredSourceRef("checkpoint:v1", Ref.CANDIDATE_EVIDENCE, req.candidate_id, "checkpoint", True)
    req = replace(req, source_registry=(*req.source_registry[:-1], forged))
    result = run(req, link(evidence_refs=["checkpoint:v1"]))
    assert result.validation_issue_codes == (Issue.CHECKPOINT_AS_EVIDENCE,)


def test_gap_requires_confirmation_outside_ai_profile_and_checkpoint():
    req = request()
    req = replace(req, candidate_profile=replace(req.candidate_profile, confirmed_gaps=("need-1",),
                  checkpoint=ProfileCheckpoint("PRIVATE", confirmed_gaps=("need-1",))))
    raw = link(assessment="gap", evidence_refs=[], candidate_capability_id=None)
    result = run(req, raw)
    assert result.output_payload.links[0].assessment is Evidence.EVIDENCE_MISSING
    req = replace(req, source_registry=(*req.source_registry, RegisteredSourceRef(
        "absence:1", Ref.CAREER_MEMORY_SOURCE, req.candidate_id, "career_update", confirmed_absence_for=("need-1",),
    )))
    result = run(req, raw)
    assert result.output_payload.links[0].assessment is Evidence.GAP


@pytest.mark.parametrize("authority", ["strongly_implied", "explicit", "unknown"])
def test_interpreted_job_blocker_cannot_be_invented(authority):
    req = request(Op.BUILD_JOB_PROFILE)
    raw = {"needs": [dict(need_id="n", label="License", importance="core", authority=authority,
                           hard_fact_refs=["f1"], hard_blocker=True)]}
    result = run(req, raw)
    assert result.validation_status is Status.REJECTED
    assert result.validation_issue_codes == (Issue.UNSUPPORTED_BLOCKER,)


def test_explicit_hard_blocker_survives_valid_interpretation():
    req = request(Op.BUILD_JOB_PROFILE)
    hard = replace(req.hard_facts, facts=(replace(req.hard_facts.facts[0], hard_blocker=True),))
    req = replace(req, hard_facts=hard)
    raw = {"needs": [dict(need_id="n", label="License", importance="core", authority="explicit",
                           hard_fact_refs=["f1"], hard_blocker=True)]}
    assert run(req, raw).validation_status is Status.ACCEPTED


def opportunity_req(known=False):
    req = request(Op.INTERPRET_OPPORTUNITY_VALUE)
    return replace(req, opportunity_facts=(OpportunityFact(
        Kind.COMPENSATION, FactState.KNOWN if known else FactState.UNKNOWN,
        ("memory:context", "f1"), ("Annual EUR values supplied" if known else "Salary absent",),
    ),))


def signal(**changes):
    raw = dict(kind="compensation", factual_state="known", state="negative", authority="strongly_implied",
               supporting_refs=["memory:context", "f1"], importance="core", uncertainty="")
    raw.update(changes)
    return {"signals": [raw]}


def test_unknown_salary_cannot_be_negative_and_all_nine_dimensions_are_visible():
    result = run(opportunity_req(), signal())
    assert result.validation_status is Status.NORMALIZED
    values = result.output_payload.signals
    assert len(values) == 9
    assert all(item.state.value == "unknown" for item in values)
    assert Issue.UNKNOWN_OPPORTUNITY_FACT in result.validation_issue_codes


def test_invented_benefit_ref_rejected_and_partial_support_rejected():
    assert run(opportunity_req(True), signal(supporting_refs=["free-health-benefit"])).validation_issue_codes == (Issue.UNKNOWN_REF,)
    assert run(opportunity_req(True), signal(supporting_refs=["f1"])).validation_issue_codes == (Issue.UNSUPPORTED_OPPORTUNITY,)


def test_valid_paraphrase_and_adjacent_links_need_no_exact_text_match():
    req = request()
    req = replace(req, candidate_profile=replace(req.candidate_profile, capabilities=(
        replace(req.candidate_profile.capabilities[0], label="Resolved unusual payment patterns"),
    )))
    assert run(req, link()).output_payload.links[0].assessment is Evidence.PROVEN
    transferable = replace(req.candidate_profile.capabilities[0], transferable=True)
    req = replace(req, candidate_profile=replace(req.candidate_profile, capabilities=(transferable,)))
    assert run(req, link(assessment="transferable")).output_payload.links[0].assessment is Evidence.TRANSFERABLE
    result = run(req, link())
    assert result.output_payload.links[0].assessment is Evidence.TRANSFERABLE
    assert Issue.TRANSFERABLE_PROMOTION in result.validation_issue_codes


@pytest.mark.parametrize("raw", ["private unstructured text", None, [], {"links": []},
    {"links": [], "classification": "best_match"}, link(confidence="certain"),
    link(needs_evidence="false"), link(evidence_refs="experience:1"),
    {"links": [link()["links"][0], link()["links"][0]]}, link(candidate_capability_id="invented"),
])
def test_malformed_structure_has_no_authoritative_payload(raw):
    result = run(request(), raw)
    assert result.validation_status is Status.REJECTED
    assert result.output_payload is None


def test_previous_checkpoint_can_describe_delta_but_never_supply_capability_refs():
    req = request(Op.BUILD_CANDIDATE_PROFILE)
    req = replace(req, memory_signature="signed-source", memory_projection={"source": "only"},
                  previous_checkpoint=ProfileCheckpoint("PRIVATE STRONG API EXPERT"))
    raw = {"capabilities": [dict(capability_id="api", label="API", evidence_refs=["experience:1"])],
           "checkpoint": {"current_position": "Current view", "changes_since_previous_version": ["More evidence now"]}}
    result = run(req, raw)
    profile = candidate_snapshot(req, result, version=2, supersedes_version=1)
    assert profile.source_refs == ("experience:1",)
    assert profile.checkpoint.changes_since_previous_version == ("More evidence now",)
    raw["capabilities"][0]["evidence_refs"] = ["checkpoint:v1"]
    assert run(req, raw).validation_issue_codes == (Issue.CHECKPOINT_AS_EVIDENCE,)


def test_logging_is_content_free_and_input_fixture_are_not_mutated(caplog):
    caplog.set_level(logging.INFO, logger="services.fixture_structured_interpreter")
    req, raw = request(), link(uncertainty="PRIVATE PROFILE PROMPT", evidence_question_hint="PRIVATE QUESTION")
    before = deepcopy((req, raw))
    result = run(req, raw)
    assert (req, raw) == before
    assert "PRIVATE" not in caplog.text
    assert req.candidate_id not in caplog.text
    assert result.input_signature not in caplog.text
    event = json.loads(caplog.records[-1].message)
    assert event["proven"] == 1 and event["authoritative"] is False


def test_envelope_binding_and_revalidation_block_replay_and_forgery():
    req = request()
    result = run(req, link())
    with pytest.raises(InterpretationValidationError):
        accepted_payload(replace(req, candidate_id="other"), result, Op.ANALYZE_HIRING_CASE)
    forged_link = replace(result.output_payload.links[0], evidence_refs=("checkpoint:v1",))
    result = replace(result, output_payload=replace(result.output_payload, links=(forged_link,)))
    with pytest.raises(InterpretationValidationError, match="checkpoint_as_evidence"):
        accepted_payload(req, result, Op.ANALYZE_HIRING_CASE)


def test_cross_candidate_registry_is_rejected():
    req = request()
    req = replace(req, source_registry=(replace(req.source_registry[0], owner_id="other"), *req.source_registry[1:]))
    assert run(req, link()).validation_issue_codes == (Issue.INVALID_SCOPE,)


def test_opportunity_and_strength_are_independent_and_category_stays_in_engine():
    from services.hiring_case_engine import build_hiring_case
    from services.profile_hiring_case_adapter import build_profile_hiring_case_input
    pair, value = request(), opportunity_req(True)
    pr, vr = run(pair, link()), run(value, signal())
    interpretation = hiring_interpretation(pair, pr, value, vr)
    result = build_hiring_case(build_profile_hiring_case_input(
        candidate_profile=pair.candidate_profile, job_profile=pair.job_profile,
        hard_facts=pair.hard_facts, interpretation=interpretation,
    ))
    assert result.hiring_case_strength.value == "strong"
    assert result.opportunity.value.value == "low"
    assert result.classification.value == "youre_strong_but"
    assert "classification" not in asdict(pr.output_payload)


def test_unknown_job_need_cannot_become_proven():
    from models.profile_interpretation import InterpretationAuthority
    req = request()
    need = replace(req.job_profile.needs[0], authority=InterpretationAuthority.UNKNOWN)
    req = replace(req, job_profile=replace(req.job_profile, needs=(need,)))
    result = run(req, link())
    assert result.output_payload.links[0].assessment is Evidence.EVIDENCE_MISSING
    assert Issue.UNKNOWN_NEED in result.validation_issue_codes


def test_candidate_operation_requires_source_projection_and_signature():
    req = request(Op.BUILD_CANDIDATE_PROFILE)
    raw = {"capabilities": [], "checkpoint": {"current_position": "Unknown"}}
    for changed in (replace(req, memory_signature=""), replace(req, memory_projection=None)):
        assert run(changed, raw).validation_status is Status.REJECTED


def test_calibration_responses_are_pinned_to_source_facts_not_just_case_id():
    from tests.hiring_case_calibration_cases import calibration_cases
    from tests.structured_calibration_fixtures import fixture_requests
    case = calibration_cases()[0]
    changed = replace(case.facts, company=replace(case.facts.company, expected_work="Changed input"))
    with pytest.raises(ValueError, match="^fixture_unavailable$"):
        fixture_requests(case.case_id, changed, "candidate", "job")


def test_caller_cannot_mutate_registered_response_after_registration():
    req, raw = request(), link()
    interpreter = FixtureStructuredInterpreter({fixture_key(req): raw})
    raw["links"][0]["evidence_refs"] = ["checkpoint:v1"]
    assert interpreter.interpret(req).validation_status is Status.ACCEPTED
