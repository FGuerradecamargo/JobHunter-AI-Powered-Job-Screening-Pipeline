from dataclasses import asdict, replace
import json
from pathlib import Path
import socket

import pytest

from models.hiring_case import (
    TemporalRequirement as Requirement, TemporalApplicability as Applicability,
    RequirementImportance as Importance, RequirementAssessment, RequirementEvidenceState as Evidence,
    HiringCaseInput,
)
from models.structured_interpretation import (
    InterpretationOperation as Op, ValidationStatus as Status, ValidationIssue as Issue,
    RegisteredSourceRef, SourceRefClass,
)
from models.profile_interpretation import InterpretationAuthority
from services.hiring_case_engine import build_hiring_case
from services.profile_hiring_case_adapter import build_profile_hiring_case_input
from services.profile_snapshot_repository import _job_from_json
from services.structured_profile_boundary import hiring_interpretation
from tests.test_offline_structured_interpreter import request, run, link
from tests.hiring_case_adversarial_cases import adversarial_cases
from tests.hiring_case_adversarial_runner import digest, observe


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External IO forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    from services import database
    monkeypatch.setattr(database, "get_connection", forbidden)


def temporal_request(version="", performed_on="", required=True):
    req = request()
    mode = Requirement.CURRENT_REQUIRED if required else Requirement.NOT_REQUIRED
    fact = replace(req.hard_facts.facts[0], temporal_requirement=mode,
                   temporal_need_id="need-1" if required else "",
                   required_version="v2" if required else "", superseded_versions=("v1",) if required else (),
                   material_change_on="2026-01-01" if required else "")
    need = replace(req.job_profile.needs[0], temporal_requirement=mode,
                   temporal_requirement_refs=("f1",) if required else ())
    registry = (replace(req.source_registry[0], temporal_need_id="need-1",
                        temporal_version=version, performed_on=performed_on), *req.source_registry[1:])
    return replace(req, hard_facts=replace(req.hard_facts, facts=(fact,)),
                   job_profile=replace(req.job_profile, needs=(need,)), source_registry=registry)


def engine(req, raw):
    pr = run(req, raw)
    vr = replace(req, operation=Op.INTERPRET_OPPORTUNITY_VALUE)
    interpretation = hiring_interpretation(req, pr, vr, run(vr, {"signals": []}))
    return build_hiring_case(build_profile_hiring_case_input(candidate_profile=req.candidate_profile,
        job_profile=req.job_profile, hard_facts=req.hard_facts, interpretation=interpretation))


@pytest.mark.parametrize("date", ["0001-01-01", "1950-01-01", "2025-01-01"])
def test_old_valid_evidence_has_no_penalty_without_explicit_temporal_requirement(date):
    req = temporal_request("v1", date, required=False)
    result = engine(req, link())
    assert result.hiring_case_strength.value == "strong"
    assert result.requirements[0].temporal_applicability is Applicability.NOT_APPLICABLE
    assert result.requirements[0].evidence_state is Evidence.PROVEN


@pytest.mark.parametrize("version,date,expected", [
    ("v2", "2026-01-01", Applicability.SATISFIED),
    ("v1", "2016-04-01", Applicability.NOT_SATISFIED),
    ("", "2025-12-31", Applicability.NOT_SATISFIED),
    ("", "", Applicability.UNKNOWN),
    ("", "2026-01-01", Applicability.UNKNOWN),
    ("v2", "2025-12-31", Applicability.UNKNOWN),
    ("unrelated-version", "", Applicability.UNKNOWN),
])
def test_explicit_version_or_change_boundary_not_generic_age(version, date, expected):
    result = run(temporal_request(version, date), link())
    assert result.output_payload.links[0].temporal_applicability is expected
    assert result.output_payload.links[0].assessment is Evidence.PROVEN


def test_unknown_temporal_support_lowers_link_confidence_not_valence_or_state():
    req = temporal_request()
    result = run(req, link())
    item = result.output_payload.links[0]
    assert item.confidence.value == "low" and "unknown" in item.uncertainty
    assert item.assessment is Evidence.PROVEN
    assert engine(req, link()).hiring_case_strength.value == "strong"


@pytest.mark.parametrize("importance,expected", [(Importance.CORE, "viable"),
    (Importance.IMPORTANT, "viable"), (Importance.NICE_TO_HAVE, "strong")])
def test_temporal_constraint_strength_keeps_historical_proof(importance, expected):
    historical = RequirementAssessment("historic", "Procedure", importance, Evidence.PROVEN, ["old-ref"],
        temporal_requirement=Requirement.CURRENT_REQUIRED, temporal_applicability=Applicability.NOT_SATISFIED)
    core = RequirementAssessment("core", "Independent work", Importance.CORE, Evidence.PROVEN, ["core-ref"])
    result = build_hiring_case(HiringCaseInput("c", "j", [core, historical]))
    assert result.hiring_case_strength.value == expected
    assert result.requirements[-1].evidence_state is Evidence.PROVEN
    assert not result.add_evidence
    assert "does not establish current" in result.how_to_prove.items[-1].what_to_demonstrate
    assert result.how_to_prove.items[-1].temporal_applicability is Applicability.NOT_SATISFIED


def test_current_refresh_can_support_proven_without_deleting_historical_source():
    req = temporal_request("v1", "2016-01-01")
    current = RegisteredSourceRef("experience:refresh", SourceRefClass.CANDIDATE_EVIDENCE,
        req.candidate_id, "career_update", True, temporal_need_id="need-1", temporal_version="v2",
        performed_on="2026-02-01")
    cap = replace(req.candidate_profile.capabilities[0], evidence_refs=("experience:1", current.ref))
    profile = replace(req.candidate_profile, capabilities=(cap,), source_refs=("experience:1", current.ref))
    req = replace(req, candidate_profile=profile, source_registry=(*req.source_registry, current))
    result = run(req, link(evidence_refs=["experience:1", current.ref]))
    item = result.output_payload.links[0]
    assert item.assessment is Evidence.PROVEN and item.temporal_applicability is Applicability.SATISFIED
    assert item.evidence_refs == ("experience:1", current.ref)


def test_interpreter_cannot_claim_temporal_satisfaction_without_metadata():
    result = run(temporal_request(), link(temporal_applicability="satisfied"))
    assert result.output_payload.links[0].temporal_applicability is Applicability.UNKNOWN


@pytest.mark.parametrize("ref", ["checkpoint:v1", "invented", "f1"])
def test_checkpoint_invalid_or_job_refs_cannot_establish_currency(ref):
    assert run(temporal_request("v2"), link(evidence_refs=[ref])).validation_status is Status.REJECTED


@pytest.mark.parametrize("authority", ["strongly_implied", "unknown"])
def test_interpreter_cannot_invent_current_requirement_from_implied_need(authority):
    req = temporal_request()
    raw = asdict(req.job_profile.needs[0])
    raw["authority"] = authority
    result = run(replace(req, operation=Op.BUILD_JOB_PROFILE, job_profile=None), {"needs": [raw]})
    assert result.validation_issue_codes == (Issue.UNSUPPORTED_TEMPORAL_REQUIREMENT,)


def test_directly_claimed_current_requirement_still_needs_marked_hard_fact():
    req = temporal_request(required=False)
    raw = asdict(req.job_profile.needs[0])
    raw.update(temporal_requirement="current_required", temporal_requirement_refs=["f1"])
    assert run(replace(req, operation=Op.BUILD_JOB_PROFILE, job_profile=None), {"needs": [raw]}).validation_status is Status.REJECTED


def test_invalid_temporal_date_fails_with_content_free_code():
    result = run(temporal_request("v2", "PRIVATE-NOT-A-DATE"), link())
    assert result.validation_issue_codes == (Issue.INVALID_TEMPORAL_METADATA,)
    assert result.output_payload is None


def test_metadata_for_other_need_does_not_establish_currency():
    req = temporal_request("v2")
    req = replace(req, source_registry=(replace(req.source_registry[0], temporal_need_id="other"), *req.source_registry[1:]))
    assert run(req, link()).output_payload.links[0].temporal_applicability is Applicability.UNKNOWN


def test_snapshots_roundtrip_and_old_snapshots_default_to_no_requirement():
    profile = temporal_request().job_profile
    assert _job_from_json(json.dumps(asdict(profile))) == profile
    old = asdict(profile)
    for need in old["needs"]:
        need.pop("temporal_requirement")
        need.pop("temporal_requirement_refs")
    assert _job_from_json(json.dumps(old)).needs[0].temporal_requirement is Requirement.NOT_REQUIRED


def test_av28_review_only_and_final_temporal_result():
    manifest = json.loads(Path(__file__).with_name("hiring_case_review_freeze.json").read_text())
    cases = adversarial_cases()
    assert digest([asdict(case) for case in cases if case.case_id != "AV28"]) == manifest["adversarial-unchanged-except-AV28"]
    result = observe(next(case for case in cases if case.case_id == "AV28"))
    assert result["states"] == ("transferable",)
    assert result["temporal"] == (("current_required", "not_satisfied"),)
    assert (result["strength"], result["value"], result["classification"]) == ("viable", "high", "worth_a_try")
