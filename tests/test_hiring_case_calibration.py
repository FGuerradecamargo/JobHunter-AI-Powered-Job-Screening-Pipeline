from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import json
import logging
import socket

import pytest

from tests.hiring_case_calibration_cases import RootCause, calibration_cases
from tests.hiring_case_calibration_runner import (
    changed_fact_paths, evaluate_case, metrics, render_report, run_calibration,
    source_from_facts,
)


@pytest.fixture(autouse=True)
def no_external_side_effects(monkeypatch):
    from services import database
    def forbidden(*args, **kwargs):
        raise AssertionError("Calibration must remain offline and computation-only.")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(database, "get_connection", forbidden)


def test_composition_and_review_provenance_are_explicit():
    cases = calibration_cases()
    assert len(cases) == len({case.case_id for case in cases}) == 40
    assert len({case.family for case in cases}) == 8
    assert Counter(case.review_track for case in cases) == {"normative": 38, "exploratory": 2}
    assert {case.case_id for case in cases if case.human_review_status == "reviewed"} == {"HC12b", "HC15b", "HC20b"}
    assert {case.expected.classification for case in cases} == {
        "best_match", "worth_a_try", "youre_strong_but", "skip_for_now", "ineligible",
    }


@pytest.mark.parametrize("number", range(1, 21))
def test_controlled_pair_changes_only_declared_fact(number):
    a, b = [case for case in calibration_cases() if case.pair_id == f"P{number:02d}"]
    paths = changed_fact_paths(asdict(a.facts), asdict(b.facts))
    assert paths
    assert a.changed_path == b.changed_path
    assert all(path == a.changed_path or path.startswith(a.changed_path + ".") for path in paths)


@pytest.mark.parametrize("case", calibration_cases(), ids=lambda case: case.case_id)
def test_case_layers_and_proof_review_remain_reproducible(case):
    assert case.facts.company.expected_work
    assert case.facts.company.seniority_context
    assert case.facts.candidate.context.scope
    assert all(str(value) for value in asdict(case.facts.opportunity).values())
    assert case.expected.rationale
    need_keys = {need.key for need in case.facts.company.needs}
    assert need_keys == {capability.key for capability in case.facts.candidate.capabilities}
    assert need_keys == dict(case.expected.states).keys()
    before = deepcopy(case)
    first = evaluate_case(case)
    assert first == evaluate_case(case)
    assert case == before
    # Disagreements are diagnostic observations, not failing expected-label assertions.
    assert len(first["proof_review"]) == len(need_keys)
    for item in first["proof_review"]:
        if item["expected_state"] in {"gap", "evidence_missing"}:
            assert item["safe_in_cv"] is False
            assert item["interview_defensible"] is False
        if item["expected_state"] == "evidence_missing":
            assert item["needs_evidence"] is not item["needs_source_repair"]
    if first["any_mismatch"]:
        assert first["primary_root_cause"] in {cause.value for cause in RootCause}


def test_expected_labels_never_feed_the_shadow_projection():
    case = calibration_cases()[0]
    changed = replace(case, expected=replace(
        case.expected, classification="skip_for_now", strength="weak", value="low",
        states=(("main", "gap"),), rationale="Deliberately changed reference, not facts.",
    ))
    assert source_from_facts(case.facts, case.legacy_recommendation) == source_from_facts(changed.facts, changed.legacy_recommendation)
    assert evaluate_case(case)["shadow_classification"] == evaluate_case(changed)["shadow_classification"]


def test_metrics_denominators_and_confusion_matrices_are_consistent():
    report = run_calibration()
    assert report == run_calibration(reversed(calibration_cases()))
    for section in ["all", "normative", "exploratory"]:
        data = report[section]
        assert data["shadow_exact_matches"] + data["shadow_mismatches"] == data["total"]
        assert data["legacy_mapped"] + data["legacy_unmapped"] == data["total"]
        assert sum(sum(row.values()) for row in data["shadow_confusion_matrix"].values()) == data["total"]
        assert sum(sum(row.values()) for row in data["legacy_confusion_matrix"].values()) == data["total"]
        assert sum(data["classification_mismatch_taxonomy"].values()) == data["shadow_mismatches"]
    assert metrics([])["shadow_agreement"] == 0
    assert "pending_human_review" in report["reference_status"]
    assert "not_live_legacy_predictions" in report["legacy_status"]


def test_missing_evidence_and_real_gaps_have_separate_review_paths():
    report = run_calibration()
    expected_missing = [item for row in report["cases"] for item in row["proof_review"] if item["expected_state"] == "evidence_missing"]
    gaps = [item for row in report["cases"] for item in row["proof_review"] if item["expected_state"] == "gap"]
    assert len(expected_missing) >= 2
    assert len(gaps) >= 2
    assert all(item["capability_exists"] == "no" for item in gaps)
    for row in report["cases"]:
        for review in row["evidence_missing_review"]:
            assert review["future_question"].endswith("?")
            assert review["evidence_to_resolve"]
            assert review["first_action"]


def test_runtime_diagnostics_do_not_contain_case_evidence(caplog):
    caplog.set_level(logging.INFO, logger="services.hiring_case_shadow_service")
    cases = calibration_cases()
    run_calibration(cases)
    for case in cases:
        for capability in case.facts.candidate.capabilities:
            assert capability.proof.example not in caplog.text
    assert "synthetic-candidate" not in caplog.text
    assert len(caplog.records) == 40
    assert all(json.loads(record.message)["authoritative"] is False for record in caplog.records)


def test_report_identifies_every_case_and_separates_review_tracks():
    report = render_report(run_calibration())
    assert "NOT a completed human-reviewed gold set" in report
    for case in calibration_cases():
        assert f"| {case.case_id} | {case.review_track} |" in report
    for cause in RootCause:
        assert cause.value in report
