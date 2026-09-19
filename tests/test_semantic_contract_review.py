"""Human-reviewed fixtures, not a deterministic language-understanding test."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import socket

import pytest

from tests.hiring_case_adversarial_cases import P, adversarial_cases
from tests.hiring_case_adversarial_runner import digest, observe as observe_adversarial
from tests.hiring_case_calibration_cases import calibration_cases
from tests.semantic_evidence_v1_runner import references, project, response, observe
from tests.test_semantic_evidence import semantic_fixture
from services.semantic_evidence_boundary import validate_semantic_support


ROOT = Path(__file__).parent
OLD_RECOVERY = "Traced a failed payment, isolated the cause, restored service and verified settlement."


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Review tests cannot access external services")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    from services import database
    monkeypatch.setattr(database, "get_connection", deny)


def ledger():
    return json.loads((ROOT / "semantic_contract_review_v1.json").read_text())


def test_original_reference_is_preserved_and_only_reviewed_judgments_change():
    original_bytes = (ROOT / "fixtures/semantic_evidence_v1_original_reference.json").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(original_bytes).hexdigest() == ledger()["previous_semantic_freeze"]["reference_sha256"]
    old = {c["id"]: c for c in json.loads(original_bytes)["cases"]}
    current = {c["id"]: c for c in references()}
    assert set(current) - set(old) == {"SE55"}
    assert set(old) - set(current) == set()
    assert {k for k in old if old[k] != current[k]} == {"SE04", "SE13", "SE14", "SE40", "SE44"}
    for key in old:
        assert {k: v for k, v in old[key].items() if k != "expected"} == {
            k: v for k, v in current[key].items() if k != "expected"}


def test_original_case_freezes_reconstruct_and_unrelated_judgments_stay_identical():
    history = ledger()
    for suite, cases, freeze_key in [
        ("adversarial", adversarial_cases(), "adversarial-v1"),
        ("calibration", calibration_cases(), "reviewed-calibration-v1"),
    ]:
        archived = {c["case_id"]: c for c in history["original_changed_" + suite]}
        restored = [archived.get(c.case_id, asdict(c)) for c in cases]
        assert digest(restored) == history["previous_freezes"][freeze_key]
        expected = history["original_" + suite + "_expected"]
        changed = {c.case_id for c in cases if json.loads(json.dumps(asdict(c.expected))) != expected[c.case_id]}
        assert changed == set(history["judgment_changes"][suite])
    restored_av = [next((x for x in history["original_changed_adversarial"] if x["case_id"] == c.case_id), asdict(c))
                   for c in adversarial_cases()]
    assert digest([c for c in restored_av if c["case_id"] != "AV28"]) == history["previous_freezes"]["adversarial-unchanged-except-AV28"]


def test_fixture_corrections_are_exact_and_do_not_smuggle_in_other_facts():
    history = ledger()
    current = {c.case_id: json.loads(json.dumps(asdict(c))) for c in adversarial_cases()}
    for old in history["original_changed_adversarial"]:
        expected = deepcopy(old)
        for need in expected["needs"]:
            if need["evidence"] == OLD_RECOVERY:
                need["evidence"] = "Independently " + OLD_RECOVERY[0].lower() + OLD_RECOVERY[1:]
        if old["case_id"] == "AV26":
            expected["needs"][0]["text"] = "Own production recovery"
        actual = current[old["case_id"]]
        assert {k: v for k, v in actual.items() if k not in {"expected", "reply"}} == {
            k: v for k, v in expected.items() if k not in {"expected", "reply"}}
        if old["case_id"] not in {"AV02", "AV26"}:
            assert actual["reply"] == expected["reply"]


def test_shared_p_now_contains_the_intended_independence_fact():
    cases = adversarial_cases()
    users = [c for c in cases if any(n is P for n in c.needs)]
    assert len(users) == 22
    assert sum(bool(c.expected.states) and c.expected.states[0] == "proven" for c in users) == 21
    assert P.evidence == "Independently traced a failed payment, isolated the cause, restored service and verified settlement."
    assert sum(any(n.evidence == P.evidence for n in c.needs) for c in cases) == 25
    assert P.text == "Resolve payment incidents independently"


@pytest.mark.parametrize("case_id,pair,state", [
    ("SE01", ("direct", "full"), "proven"),
    ("SE03", ("adjacent", "full"), "transferable"),
    ("SE04", ("adjacent", "partial"), "evidence_missing"),
    ("SE13", ("adjacent", "partial"), "evidence_missing"),
    ("SE14", ("adjacent", "partial"), "evidence_missing"),
    ("SE16", ("adjacent", "partial"), "evidence_missing"),
    ("SE18", ("adjacent", "full"), "transferable"),
    ("SE19", ("adjacent", "partial"), "evidence_missing"),
    ("SE20", ("none", "none"), "evidence_missing"),
    ("SE21", ("adjacent", "full"), "transferable"),
    ("SE30", ("none", "none"), "gap"),
    ("SE40", ("none", "none"), "evidence_missing"),
    ("SE44", ("adjacent", "partial"), "evidence_missing"),
    ("SE55", ("direct", "partial"), "evidence_missing"),
])
def test_reviewed_semantics_consumed_from_controlled_replies(case_id, pair, state):
    case = next(c for c in references() if c["id"] == case_id)
    actual = observe({k: v for k, v in case.items() if k != "expected"})
    assert (actual["relation"], actual["coverage"]) == pair
    assert actual["assessment"] == state


def test_missing_independence_regression_preserves_batch_001_old_evidence_not_gap():
    case = next(c for c in references() if c["id"] == "SE55")
    assert case["job_need"] == P.text
    assert case["candidate_evidence"] == [OLD_RECOVERY]
    assert not case["confirmed_absence"]
    request = project({k: v for k, v in case.items() if k != "expected"})
    result = validate_semantic_support(request, response("SE55", request))
    assert result.needs[0].assessment.value == "evidence_missing"
    assert result.needs[0].supporting_refs == ("e0",)
    assert result.needs[0].support.links[0].coverage.value == "partial"


@pytest.mark.parametrize("case_id,relations,states", [
    ("AV02", [("direct", "full"), ("adjacent", "partial")], ("proven", "evidence_missing")),
    ("AV06", [("direct", "full"), ("none", "none")], ("proven", "evidence_missing")),
    ("AV26", [("adjacent", "partial")], ("evidence_missing",)),
])
def test_reviewed_adversarial_semantics_preserve_product_meaning(case_id, relations, states):
    case = next(c for c in adversarial_cases() if c.case_id == case_id)
    fixtures = semantic_fixture(relations)
    # Unlike the deliberate AV06 reuse, AV02's second need has its own source.
    if case_id == "AV02":
        fixtures[1]["links"][0].update(evidence_ref="e:1", candidate_capability_id="n1")
    actual = observe_adversarial(case, semantic_fixture=fixtures)
    assert actual["states"] == states
    assert (actual["strength"], actual["value"], actual["classification"]) == ("viable", "high", "worth_a_try")
    if case_id == "AV02":
        assert actual["constraints"][1] == ("direct_required", False, "direct_evidence_required")
    if case_id == "AV26":
        assert case.needs[0].text == "Own production recovery"
        assert case.needs[0].transferable and not case.needs[0].confirmed_gap


@pytest.mark.parametrize("case_id", ["AV17", "AV19"])
def test_scale_gate_does_not_require_partial_semantic_coverage(case_id):
    case = next(c for c in adversarial_cases() if c.case_id == case_id)
    assert case.scope_mismatch
    actual = observe_adversarial(case, semantic_fixture=semantic_fixture([("direct", "full")]))
    assert actual["states"] == ("proven",)
    assert actual["strength"] == "weak"


def test_corrected_calibration_facts_preserve_intended_outcomes():
    from tests.structured_calibration_fixtures import fixture_requests
    from services.profile_hiring_case_adapter import build_profile_hiring_case_input
    from services.hiring_case_engine import build_hiring_case
    for case in calibration_cases():
        if case.case_id not in {"HC02b", "HC18a"}:
            continue
        candidate, job, hard, interpretation, _ = fixture_requests(case.case_id, case.facts, "candidate", "job")
        actual = build_hiring_case(build_profile_hiring_case_input(candidate_profile=candidate, job_profile=job,
            hard_facts=hard, interpretation=interpretation))
        assert actual.classification.value == case.expected.classification
        assert actual.hiring_case_strength.value == case.expected.strength
        assert actual.requirements[0].evidence_state.value == dict(case.expected.states)["main"]
