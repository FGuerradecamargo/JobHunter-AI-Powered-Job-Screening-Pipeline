from copy import deepcopy
from dataclasses import replace
import json
import logging
import socket

import pytest

from models.hiring_case import RequirementEvidenceState as State
from models.structured_interpretation import ValidationStatus as Status
from services.fixture_semantic_interpreter import FixtureSemanticInterpreter
from services.semantic_evidence_boundary import signature, validate_semantic_support, semantic_requirement_links, SemanticSupportError
from tests.semantic_evidence_v1_runner import references, project, response, observe, run_benchmark
from tests.hiring_case_adversarial_cases import adversarial_cases
from tests.hiring_case_adversarial_runner import observe as observe_adversarial


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("External IO forbidden")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    from services import database
    monkeypatch.setattr(database, "get_connection", deny)


def setup(case_id="SE01"):
    case = next(c for c in references() if c["id"] == case_id)
    request = project({k: v for k, v in case.items() if k != "expected"})
    return request, response(case_id, request)


@pytest.mark.parametrize("case", references(), ids=lambda c: c["id"])
def test_frozen_semantic_contract_reference(case):
    actual = observe({k: v for k, v in case.items() if k != "expected"})
    assert {k: actual[k] for k in case["expected"]} == case["expected"]


def test_metrics_are_contract_agreement_not_ai_accuracy():
    result = run_benchmark()
    assert (result["total"], result["accepted"], result["safely_rejected"]) == (55, 51, 4)
    assert result["agreement_accepted"] == dict(relation=51, coverage=51, assessment=51)


@pytest.mark.parametrize("mutation", ["candidate", "job", "content", "signature"])
def test_old_response_cannot_cross_profile_or_source_version(mutation):
    req, raw = setup()
    if mutation == "candidate":
        req = replace(req, context=replace(req.context, candidate_profile=replace(req.context.candidate_profile, profile_version=2)))
    elif mutation == "job":
        req = replace(req, context=replace(req.context, job_profile=replace(req.context.job_profile, profile_version=2)))
    elif mutation == "content":
        req = replace(req, evidence=(replace(req.evidence[0], summary="changed private source"),))
    else:
        req = replace(req, context=replace(req.context, memory_signature="changed"))
    assert validate_semantic_support(req, raw).status is Status.REJECTED


@pytest.mark.parametrize("ref,code", [("unknown", "unknown_ref"), ("checkpoint:v1", "checkpoint_as_evidence"), ("fact", "wrong_source_class")])
def test_invalid_refs_caught(ref, code):
    req, raw = setup()
    raw["needs"][0]["links"][0]["evidence_ref"] = ref
    assert validate_semantic_support(req, raw).issue_codes == (code,)


def test_partial_preserved_and_cannot_be_promoted_to_whole():
    req, raw = setup("SE10")
    raw["needs"][0]["coverage"] = "full"
    raw["needs"][0]["reason_code"] = "direct_support"
    result = validate_semantic_support(req, raw)
    assert result.needs[0].assessment is State.EVIDENCE_MISSING
    assert result.needs[0].supporting_refs == ("e0",)
    assert result.needs[0].support.links[0].coverage.value == "partial"
    assert "partial_to_full_overclaim" in result.issue_codes


def test_unsupported_ownership_promotion_caught():
    req, raw = setup("SE21")
    raw["needs"][0]["support_relation"] = "direct"
    raw["needs"][0]["reason_code"] = "direct_support"
    result = validate_semantic_support(req, raw)
    assert result.needs[0].assessment is State.TRANSFERABLE
    assert "ownership_promotion" in result.issue_codes


def test_none_cannot_be_promoted_and_does_not_invent_gap():
    req, raw = setup("SE05")
    raw["needs"][0].update(support_relation="direct", coverage="full", reason_code="direct_support")
    result = validate_semantic_support(req, raw)
    assert result.needs[0].assessment is State.EVIDENCE_MISSING
    assert result.needs[0].support.links[0].evidence_ref == "e0"
    assert "unsupported_promotion" in result.issue_codes


def test_multiple_sources_require_explicit_joint_interpretation():
    req, raw = setup("SE11")
    assert validate_semantic_support(req, raw).needs[0].assessment is State.PROVEN
    raw["needs"][0]["joint_support"] = False
    assert validate_semantic_support(req, raw).needs[0].assessment is State.EVIDENCE_MISSING


def test_conflicts_cannot_select_favorable_source_by_order():
    req, raw = setup("SE33")
    raw["needs"][0].update(support_relation="direct", coverage="full", reason_code="direct_support")
    for links in (raw["needs"][0]["links"], list(reversed(raw["needs"][0]["links"]))):
        raw["needs"][0]["links"] = links
        result = validate_semantic_support(req, raw)
        assert result.needs[0].assessment is State.EVIDENCE_MISSING
        assert result.needs[0].support.support_relation.value == "uncertain"


def test_content_free_logs_and_question_hint_has_no_authority(caplog):
    req, raw = setup("SE10")
    raw["needs"][0]["evidence_question_hint"] = "PRIVATE I independently approved refunds"
    with caplog.at_level(logging.INFO):
        result = validate_semantic_support(req, raw)
    assert result.needs[0].assessment is State.EVIDENCE_MISSING
    assert "PRIVATE" not in caplog.text and req.evidence[0].summary not in caplog.text
    assert req.context.candidate_profile.checkpoint.current_position == "Derived only"


@pytest.mark.parametrize("field,value", [("invented_ownership", True), ("supported_facets", ["invented"]), ("chain_of_thought", "private")])
def test_no_new_candidate_facts_or_invented_facets(field, value):
    req, raw = setup()
    raw["needs"][0][field] = value
    assert validate_semantic_support(req, raw).status is Status.REJECTED


def test_unavailable_semantics_does_not_infer_from_provenance():
    req, raw = setup()
    client = FixtureSemanticInterpreter({signature(req): raw})
    raw["needs"][0]["coverage"] = "none"
    assert client.evaluate(req).needs[0].assessment is State.PROVEN
    assert FixtureSemanticInterpreter({}).evaluate(req).status is Status.UNAVAILABLE
    changed = replace(req, evidence=(replace(req.evidence[0], summary="different facts"),))
    assert client.evaluate(changed).status is Status.UNAVAILABLE
    with pytest.raises(SemanticSupportError, match="semantic_support_unavailable"):
        semantic_requirement_links(req, {"status": "accepted"})


def semantic_fixture(relations):
    result = []
    for index, (relation, coverage) in enumerate(relations):
        reason = "no_support" if relation == "none" else "partial_support" if coverage == "partial" else "direct_support"
        result.append(dict(need_id=f"n{index}", support_relation=relation, coverage=coverage, confidence="high", reason_code=reason,
            links=[dict(need_id=f"n{index}", evidence_ref="e:0", candidate_capability_id="n0",
                support_relation=relation, coverage=coverage, confidence="high", reason_code=reason,
                interpreter_version="adversarial-semantic-fixture-v1")]))
    return result


@pytest.mark.parametrize("case_id,relations,states", [
    ("AV05", [("none", "none")], ("evidence_missing",)),
    ("AV06", [("direct", "full"), ("none", "none")], ("proven", "evidence_missing")),
    ("AV27", [("direct", "partial")], ("evidence_missing",)),
])
def test_av05_av06_av27_with_explicit_semantic_interpretation(case_id, relations, states):
    case = next(c for c in adversarial_cases() if c.case_id == case_id)
    result = observe_adversarial(case, semantic_fixture=semantic_fixture(relations))
    assert result["states"] == states
    assert (result["strength"], result["value"], result["classification"]) == ("viable", "high", "worth_a_try")


def test_legitimate_reuse_is_allowed_per_need_not_globally_banned():
    req, raw = setup()
    second = replace(req.context.job_profile.needs[0], need_id="related-need")
    req = replace(req, context=replace(req.context, job_profile=replace(req.context.job_profile, needs=(*req.context.job_profile.needs, second))))
    item = deepcopy(raw["needs"][0])
    item["need_id"] = item["links"][0]["need_id"] = "related-need"
    raw["needs"].append(item)
    raw["input_signature"] = signature(req)
    result = validate_semantic_support(req, raw)
    assert [n.assessment for n in result.needs] == [State.PROVEN, State.PROVEN]
    assert [n.supporting_refs for n in result.needs] == [("e0",), ("e0",)]


@pytest.mark.parametrize("change,code", [
    ("need", "unknown_need"), ("capability", "unknown_capability"),
    ("authority", "invalid_schema"), ("version", "invalid_version"),
    ("duplicate", "duplicate_relationship"), ("foreign", "invalid_scope"),
])
def test_relationship_scope_and_authority(change, code):
    req, raw = setup()
    link = raw["needs"][0]["links"][0]
    if change == "need":
        link["need_id"] = "other-job-need"
    elif change == "capability":
        link["candidate_capability_id"] = "invented-capability"
    elif change == "authority":
        link["source_authority"] = "derived_checkpoint"
    elif change == "version":
        link["interpreter_version"] = "different-provider"
    elif change == "duplicate":
        raw["needs"][0]["links"].append(deepcopy(link))
    else:
        req = replace(req, context=replace(req.context, candidate_id="another-user"))
    assert validate_semantic_support(req, raw).issue_codes == (code,)


def test_optional_capability_cannot_hide_transferable_source_scope():
    req, raw = setup()
    candidate = replace(req.context.candidate_profile, capabilities=(replace(req.context.candidate_profile.capabilities[0], transferable=True),))
    req = replace(req, context=replace(req.context, candidate_profile=candidate))
    raw["input_signature"] = signature(req)
    raw["needs"][0]["links"][0]["candidate_capability_id"] = None
    assert validate_semantic_support(req, raw).needs[0].assessment is State.TRANSFERABLE


def test_explicit_unknown_confidence_cannot_certify_proof():
    req, raw = setup()
    raw["needs"][0]["confidence"] = "unknown"
    result = validate_semantic_support(req, raw)
    assert result.needs[0].assessment is State.EVIDENCE_MISSING
    assert result.needs[0].support.support_relation.value == "uncertain"


def test_direct_requirement_and_temporal_rules_remain_independent():
    from models.hiring_case import EvidenceRequirement, TemporalApplicability
    from models.profile_interpretation import HiringCaseInterpretation, TemporalEvidenceMetadata
    from services.profile_hiring_case_adapter import build_profile_hiring_case_input
    req, raw = setup("SE21")
    hard = replace(req.context.hard_facts, facts=(replace(req.context.hard_facts.facts[0],
        evidence_requirement=EvidenceRequirement.DIRECT_REQUIRED, constraint_need_id="need"),))
    job = replace(req.context.job_profile, needs=(replace(req.context.job_profile.needs[0],
        evidence_requirement=EvidenceRequirement.DIRECT_REQUIRED, evidence_requirement_refs=("fact",)),))
    req = replace(req, context=replace(req.context, hard_facts=hard, job_profile=job))
    raw["input_signature"] = signature(req)
    links = semantic_requirement_links(req, raw)
    data = build_profile_hiring_case_input(candidate_profile=req.context.candidate_profile, job_profile=job,
        hard_facts=hard, interpretation=HiringCaseInterpretation(links))
    assert data.requirements[0].evidence_state is State.TRANSFERABLE
    assert not data.requirements[0].constraint_satisfied
    req, raw = setup("SE50")
    registry = (replace(req.context.source_registry[0], temporal_version="old"), *req.context.source_registry[1:])
    req = replace(req, context=replace(req.context, source_registry=registry))
    raw["input_signature"] = signature(req)
    result = validate_semantic_support(req, raw)
    assert result.needs[0].temporal_applicability is TemporalApplicability.NOT_SATISFIED
    assert result.needs[0].assessment is State.TRANSFERABLE
    assert result.needs[0].supporting_refs == ("e0",)


def test_confirmed_absence_conflicting_with_claim_remains_uncertain():
    req, _ = setup("SE30")
    _, raw = setup()
    raw["input_signature"] = signature(req)
    result = validate_semantic_support(req, raw)
    assert result.needs[0].assessment is State.EVIDENCE_MISSING
    assert result.needs[0].support.support_relation.value == "uncertain"
    assert "conflicting_evidence" in result.issue_codes


def test_genuine_semantic_lie_is_not_detected_by_a_provenance_validator():
    req, raw = setup("SE05")
    item = raw["needs"][0]
    item.update(support_relation="direct", coverage="full", reason_code="direct_support")
    item["links"][0].update(support_relation="direct", coverage="full", reason_code="direct_support")
    # Intentional limit: no string matcher pretends to recognize the lunch-rota mismatch.
    assert validate_semantic_support(req, raw).needs[0].assessment is State.PROVEN


def test_unsupported_reuse_cannot_override_independent_pair_judgment():
    req, raw = setup()
    second = replace(req.context.job_profile.needs[0], need_id="tax", label="File tax returns")
    req = replace(req, context=replace(req.context, job_profile=replace(req.context.job_profile, needs=(*req.context.job_profile.needs, second))))
    item = deepcopy(raw["needs"][0])
    item["need_id"] = item["links"][0]["need_id"] = "tax"
    item["links"][0].update(support_relation="none", coverage="none", reason_code="no_support")
    raw["needs"].append(item)
    raw["input_signature"] = signature(req)
    result = validate_semantic_support(req, raw)
    assert [n.assessment for n in result.needs] == [State.PROVEN, State.EVIDENCE_MISSING]
    assert "unsupported_promotion" in result.issue_codes
