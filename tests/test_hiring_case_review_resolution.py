from dataclasses import asdict, replace
from pathlib import Path
import json
import socket

import pytest

from models.hiring_case import (
    HiringCaseInput, OpportunitySignal, OpportunitySignalKind as Kind,
    OpportunitySignalState as State, RequirementImportance as Importance,
)
from models.structured_interpretation import LinkReason, ValidationStatus
from services.hiring_case_engine import assess_opportunity_value
from tests.test_offline_structured_interpreter import request, run, link
from tests.hiring_case_calibration_cases import calibration_cases
from tests.hiring_case_calibration_runner import run_calibration
from tests.hiring_case_adversarial_cases import adversarial_cases
from tests.hiring_case_adversarial_runner import digest, observe, evaluate, run_adversarial


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline review: IO forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    from services import database
    monkeypatch.setattr(database, "get_connection", forbidden)


def test_review_changed_only_three_judgments_and_all_cases_are_frozen():
    original = {case.case_id: asdict(case.expected) for case in calibration_cases()
                if case.case_id not in {"HC12b", "HC15b", "HC20b"}}
    assert digest(original) == "f36bd6a919cce6272bad6b766d8c3e3cb19d11a93e662c890b73c95053edc69d"
    manifest = json.loads(Path(__file__).with_name("hiring_case_review_freeze.json").read_text())
    assert digest([asdict(case) for case in calibration_cases()]) == manifest["reviewed-calibration-v1"]
    assert digest([asdict(case) for case in adversarial_cases()]) == manifest["adversarial-v1"]


def test_reviewed_calibration_and_provenance_metadata():
    result = run_calibration()
    assert result["all"]["shadow_exact_matches"] == 40
    assert result["all"]["strength_mismatches"] == result["all"]["value_mismatches"] == 0
    assert result["all"]["evidence_state_mismatches"] == 0
    assert result["all"]["confidence_matches"] == result["all"]["confidence_reviewed"] == 1
    rows = {row["case_id"]: row for row in result["cases"]}
    missing = rows["HC12b"]["semantic_links"][0]
    assert missing["reason_code"] == "source_reference_unavailable"
    assert missing["needs_source_repair"] and not missing["needs_evidence"]
    assert rows["HC15b"]["semantic_links"][1]["assessment"] == "transferable"
    assert rows["HC20b"]["shadow_confidence"] == "medium"


def test_source_repair_requires_trusted_marker_and_never_promotes_proof():
    req = request()
    raw = link(evidence_refs=[], needs_source_repair=True, reason_code="source_reference_unavailable")
    ordinary = run(req, raw).output_payload.links[0]
    assert ordinary.needs_evidence and not ordinary.needs_source_repair
    repaired_input = replace(req, source_repair_need_ids=("need-1",))
    result = run(repaired_input, raw)
    item = result.output_payload.links[0]
    assert item.assessment.value == "evidence_missing"
    assert item.reason_code is LinkReason.SOURCE_REFERENCE_UNAVAILABLE
    assert item.needs_source_repair and not item.needs_evidence
    assert not item.evidence_question_hint
    later = run(req, link()).output_payload.links[0]
    assert later.assessment.value == "proven" and not later.needs_source_repair
    assert req.candidate_profile == repaired_input.candidate_profile


def test_invalid_source_ref_cannot_be_excused_by_repair_flag():
    req = replace(request(), source_repair_need_ids=("need-1",))
    assert run(req, link(evidence_refs=["invented"], needs_source_repair=True)).validation_status is ValidationStatus.REJECTED


def test_unknown_cost_reduces_confidence_before_valence_and_known_negative_changes_value():
    signals = [OpportunitySignal(kind, State.POSITIVE, Importance.CORE) for kind in Kind]
    known = assess_opportunity_value(HiringCaseInput("c", "j", requirements=[], opportunity_signals=signals))
    index = [signal.kind for signal in signals].index(Kind.WORK_MODE_LOCATION)
    signals[index] = replace(signals[index], state=State.UNKNOWN)
    unknown = assess_opportunity_value(HiringCaseInput("c", "j", requirements=[], opportunity_signals=signals))
    assert known.value.value == unknown.value.value == "high"
    assert known.confidence.value == "high" and unknown.confidence.value == "medium"
    signals[index] = replace(signals[index], state=State.NEGATIVE)
    negative = assess_opportunity_value(HiringCaseInput("c", "j", requirements=[], opportunity_signals=signals))
    assert negative.value.value == "low"


def test_several_important_transferable_needs_preserve_strength_and_limits():
    actual = observe(adversarial_cases()[0])
    assert actual["strength"] == "strong"
    assert actual["states"] == ("proven", "transferable", "transferable")


@pytest.mark.parametrize("case", adversarial_cases(), ids=lambda case: case.case_id)
def test_frozen_adversarial_evaluation_is_reproducible_not_a_quota(case):
    result = evaluate(case)
    assert result == evaluate(case)
    assert case.company and case.candidate and case.opportunity and case.expected.rationale
    assert len(case.expected.states) in (0, len(case.needs))
    assert result["root_cause"] not in (None, "none") if result["mismatches"] else result["root_cause"] is None
    assert "rejected" in result["actual"]["statuses"] if not case.expected.states else True


def test_expected_judgment_does_not_feed_observation():
    case = adversarial_cases()[0]
    changed = replace(case, expected=replace(case.expected, classification="skip_for_now", value="low", states=("gap",)))
    assert observe(case) == observe(changed)


def test_adversarial_denominators_and_content_free_logs(caplog):
    caplog.set_level("INFO", logger="services.fixture_structured_interpreter")
    report = run_adversarial()
    assert report["total"] >= 30
    assert report["safe_rejections"] == 2
    assert report["evidence_matches"] <= report["evidence_total"]
    assert sum(report["taxonomy"].values()) == sum(bool(row["mismatches"]) for row in report["cases"])
    for case in adversarial_cases():
        assert case.candidate not in caplog.text and case.opportunity not in caplog.text
