"""Synthetic contract/reference agreement, not language-understanding evaluation."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from models.hiring_case import RequirementImportance as Importance, TemporalRequirement
from models.profile_interpretation import (
    CandidateProfileSnapshot, ProfileCapability, ProfileCheckpoint, AIJobProfileSnapshot,
    HardJobFact, JobHardFacts, InterpretedJobNeed, InterpretationAuthority, SourceEvidence,
    HiringCaseInterpretation, TemporalEvidenceMetadata,
)
from models.semantic_evidence import SemanticSupportRequest
from models.structured_interpretation import (
    StructuredInterpretationInput, InterpretationOperation, RegisteredSourceRef, SourceRefClass,
)
from services.fixture_semantic_interpreter import FixtureSemanticInterpreter
from services.semantic_evidence_boundary import signature, semantic_requirement_links
from services.profile_hiring_case_adapter import build_profile_hiring_case_input

ROOT = Path(__file__).parent


def references():
    raw = (ROOT / "semantic_evidence_v1_reference.json").read_bytes().replace(b"\r\n", b"\n")
    frozen = json.loads((ROOT / "semantic_evidence_v1_freeze.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == frozen["reference_sha256"]
    return json.loads(raw)["cases"]


def project(facts):
    """No expected judgments or prose matching are consumed by projection."""
    refs = tuple(facts["source_refs"])
    candidate = CandidateProfileSnapshot("candidate", 1, "memory-v1", "2026-01-01", refs,
        (ProfileCapability("cap", "Source-backed capability", refs),) if refs else (), ProfileCheckpoint("Derived only"),
        confirmed_gaps=("need",) if facts["confirmed_absence"] else ())
    current = facts["id"] in {"SE35", "SE50"}
    hard = JobHardFacts("job", "job-v1", (HardJobFact("fact", "requirement", facts["job_need"], "job-source",
        temporal_requirement=TemporalRequirement.CURRENT_REQUIRED if current else TemporalRequirement.NOT_REQUIRED,
        temporal_need_id="need" if current else "", required_version="current" if current else "",
        superseded_versions=("old",) if current else ()),))
    job = AIJobProfileSnapshot("job", 1, "job-v1", "2026-01-01", (
        InterpretedJobNeed("need", facts["job_need"], Importance.CORE, InterpretationAuthority.EXPLICIT, ("fact",),
            temporal_requirement=TemporalRequirement.CURRENT_REQUIRED if current else TemporalRequirement.NOT_REQUIRED,
            temporal_requirement_refs=("fact",) if current else ()),))
    registry = tuple(RegisteredSourceRef(ref, SourceRefClass.CANDIDATE_EVIDENCE, "candidate",
        "professional_experience", True, ("need",) if facts["confirmed_absence"] else (),
        temporal_need_id="need" if current else "", temporal_version=("old" if facts["id"] == "SE35" else "current") if current else "") for ref in refs)
    registry += (RegisteredSourceRef("fact", SourceRefClass.JOB_HARD_FACT, "job", "job_description"),
                 RegisteredSourceRef("checkpoint:v1", SourceRefClass.DERIVED_CHECKPOINT, "candidate", "checkpoint"))
    if facts["id"] == "SE51":
        registry = (replace(registry[0], owner_id="other-candidate"), *registry[1:])
    context = StructuredInterpretationInput(InterpretationOperation.ANALYZE_HIRING_CASE, "candidate", "job",
        memory_signature="memory-v1", source_registry=registry, candidate_profile=candidate, job_profile=job, hard_facts=hard)
    return SemanticSupportRequest(context, tuple(SourceEvidence(ref, "professional_experience", text)
                                                for ref, text in zip(refs, facts["candidate_evidence"])))


def response(case_id, request):
    raw = deepcopy(json.loads((ROOT / "semantic_evidence_v1_replies.json").read_text())[case_id])
    raw["input_signature"] = signature(request)
    if case_id in {"SE52", "SE53"}:
        raw["needs"][0]["links"][0]["evidence_ref"] = "checkpoint:v1" if case_id == "SE52" else "unknown-ref"
    if case_id == "SE54":
        raw["input_signature"] = "stale-profile-signature"
    return raw


def observe(facts):
    request = project(facts)
    raw = response(facts["id"], request)
    result = FixtureSemanticInterpreter({signature(request): raw}).evaluate(request)
    if not result.needs:
        return {"relation": "rejected", "coverage": "rejected", "assessment": "rejected",
                "status": result.status.value, "codes": result.issue_codes}
    need = result.needs[0]
    interpretation = HiringCaseInterpretation(semantic_requirement_links(request, raw), temporal_evidence=tuple(
        TemporalEvidenceMetadata(item.ref, item.temporal_need_id, item.temporal_version, item.performed_on)
        for item in request.context.source_registry if item.usable_evidence))
    downstream = build_profile_hiring_case_input(candidate_profile=request.context.candidate_profile,
        job_profile=request.context.job_profile, hard_facts=request.context.hard_facts, interpretation=interpretation)
    return {"relation": need.support.support_relation.value, "coverage": need.support.coverage.value,
            "assessment": downstream.requirements[0].evidence_state.value, "status": result.status.value, "codes": result.issue_codes}


def run_benchmark():
    rows = []
    for case in references():
        facts = {k: v for k, v in case.items() if k != "expected"}
        actual = observe(facts)
        rows.append({"id": case["id"], "expected": case["expected"], "actual": actual})
    accepted = [row for row in rows if row["actual"]["status"] in {"accepted", "normalized"}]
    def agreements(group):
        return {key: sum(row["actual"][key] == row["expected"][key] for row in group)
                for key in ("relation", "coverage", "assessment")}
    return {"total": len(rows), "accepted": len(accepted), "safely_rejected": len(rows) - len(accepted),
            "agreement_accepted": agreements(accepted), "agreement_all_including_rejections": agreements(rows),
            "breakdown": {axis: {label: {"total": len(group), "agreements": agreements(group)}
                for label in sorted({r["expected"][axis] for r in accepted})
                for group in [[r for r in accepted if r["expected"][axis] == label]]}
                for axis in ("relation", "coverage")},
            "rejection_codes": dict(Counter(code for row in rows if row["actual"]["status"] == "rejected"
                                             for code in row["actual"]["codes"])), "rows": rows}


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in run_benchmark().items() if k != "rows"}, indent=2))
