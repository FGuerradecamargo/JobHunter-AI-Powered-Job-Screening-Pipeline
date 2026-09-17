"""Offline adversarial-v1 evaluator. No scoring changes and no semantic matcher."""
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json

from models.hiring_case import OpportunitySignalKind as Kind, EvidenceRequirement, TemporalRequirement
from models.profile_interpretation import HardJobFact, JobHardFacts
from models.structured_interpretation import (
    FactState, InterpretationOperation as Op, OpportunityFact, RegisteredSourceRef,
    SourceRefClass as Ref, StructuredInterpretationInput as Input,
    ValidationStatus,
)
from services.fixture_structured_interpreter import FixtureStructuredInterpreter, fixture_key
from services.structured_profile_boundary import candidate_snapshot, job_snapshot, hiring_interpretation
from services.profile_hiring_case_adapter import build_profile_hiring_case_input
from services.hiring_case_engine import build_hiring_case
from tests.hiring_case_adversarial_cases import adversarial_cases


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def observe(case, *, semantic_fixture=None):
    """Only raw facts and controlled replies enter this function; never expected judgments."""
    candidate_id, job_id = "adversarial-candidate", "adversarial-job"
    registry, caps, job_needs, hard_records, links, gaps, repairs = [], [], [], [], [], [], []
    for index, need in enumerate(case.needs):
        key, ref, fact = f"n{index}", f"e:{index}", f"j:{index}"
        temporal_review = case.case_id == "AV28"
        if temporal_review and (case.company != "Current regulatory procedure required, changed this year."
                                or need.evidence != "Used obsolete procedure ten years ago."):
            raise ValueError("fixture_unavailable")
        if need.confirmed_gap:
            gaps.append(key)
        if not need.source_available and need.evidence:
            repairs.append(key)
        if need.source_available:
            registry.append(RegisteredSourceRef(ref, Ref.CAREER_MEMORY_SOURCE, candidate_id,
                                                "career_update", True, (key,) if need.confirmed_gap else (),
                                                temporal_need_id=key if temporal_review else "",
                                                temporal_version="obsolete-procedure" if temporal_review else ""))
            caps.append({"capability_id": key, "label": need.evidence,
                         "evidence_refs": [ref], "transferable": need.transferable})
        evidence_requirement = EvidenceRequirement.DIRECT_REQUIRED if need.direct_required else EvidenceRequirement.DEFENSIBLE
        need_label = case.company if temporal_review else need.text
        temporal_requirement = TemporalRequirement.CURRENT_REQUIRED if temporal_review else TemporalRequirement.NOT_REQUIRED
        hard_records.append(HardJobFact(fact, "stated_requirement", need_label, "synthetic-job-source",
                                       evidence_requirement=evidence_requirement,
                                       constraint_need_id=key if need.direct_required else "",
                                       temporal_requirement=temporal_requirement,
                                       temporal_need_id=key if temporal_review else "",
                                       required_version="current-procedure" if temporal_review else "",
                                       superseded_versions=("obsolete-procedure",) if temporal_review else ()))
        job_needs.append({"need_id": key, "label": need_label, "importance": need.importance,
                          "authority": need.authority, "hard_fact_refs": [fact],
                          "hard_blocker": case.reply.inferred_blocker,
                          "evidence_requirement": evidence_requirement.value,
                          "evidence_requirement_refs": [fact] if need.direct_required else [],
                          "temporal_requirement": temporal_requirement.value,
                          "temporal_requirement_refs": [fact] if temporal_review else []})
        target = "n0" if case.reply.reuse_first_ref else key
        evidence_ref = "e:0" if case.reply.reuse_first_ref else ref
        links.append({"need_id": key, "candidate_capability_id": target if need.source_available else None,
                      "assessment": case.reply.states[index],
                      "evidence_refs": ["checkpoint:v1"] if case.reply.checkpoint_ref else [evidence_ref] if need.source_available else [],
                      "confidence": "high", "reason_code": "direct_support", "needs_evidence": False})
    if case.hard_blocker:
        hard_records.append(HardJobFact("eligibility", "license", case.company, "synthetic-job-source", hard_blocker=True))
    hard_records.append(HardJobFact("offer", "opportunity_context", case.company, "synthetic-job-source"))
    hard = JobHardFacts(job_id, digest([asdict(item) for item in hard_records]), tuple(hard_records))
    registry.extend(RegisteredSourceRef(item.fact_id, Ref.JOB_HARD_FACT, job_id, "job_description") for item in hard_records)
    registry.extend((RegisteredSourceRef("context", Ref.CAREER_MEMORY_SOURCE, candidate_id, "candidate_context"),
                     RegisteredSourceRef("checkpoint:v1", Ref.DERIVED_CHECKPOINT, candidate_id, "checkpoint")))
    # Explicit source projection of AV30's frozen facts, not text-based conflict detection.
    conflicting_refs = ()
    if case.case_id == "AV30":
        if case.candidate != "Two current equally authoritative preferences conflict: pursue versus avoid recovery.":
            raise ValueError("fixture_unavailable")
        conflicting_refs = ("preference:pursue", "preference:avoid")
        registry.extend(RegisteredSourceRef(ref, Ref.CAREER_MEMORY_SOURCE, candidate_id,
                                           "candidate_preference") for ref in conflicting_refs)
    registry = tuple(registry)
    projection = {"context": case.candidate, "evidence": [asdict(item) for item in case.needs]}
    cr = Input(Op.BUILD_CANDIDATE_PROFILE, candidate_id, job_id, digest(projection), projection,
               registry, hard_facts=hard)
    jr = Input(Op.BUILD_JOB_PROFILE, candidate_id, job_id, source_registry=registry, hard_facts=hard)
    statuses, codes = [], []

    def interpret(req, response):
        result = FixtureStructuredInterpreter({fixture_key(req): response}, clock=lambda: "2026-01-01T00:00:00+00:00").interpret(req)
        statuses.append(result.validation_status.value)
        codes.extend(item.value for item in result.validation_issue_codes)
        return result

    rejected = dict(classification="not_evaluated", strength="not_evaluated", value="not_evaluated",
                    confidence="not_evaluated", states=(), source_repair=(), constraints=(), temporal=(), statuses=statuses, issue_codes=codes)
    cresult = interpret(cr, {"capabilities": caps, "confirmed_gaps": gaps,
                              "checkpoint": {"current_position": "Synthetic current context"}})
    jresult = interpret(jr, {"needs": job_needs})
    if any(result.validation_status is ValidationStatus.REJECTED for result in (cresult, jresult)):
        return rejected
    candidate, job = candidate_snapshot(cr, cresult), job_snapshot(jr, jresult)
    pr = Input(Op.ANALYZE_HIRING_CASE, candidate_id, job_id, source_registry=registry,
               candidate_profile=candidate, job_profile=job, hard_facts=hard,
               seniority_context_mismatch=case.scope_mismatch, source_repair_need_ids=tuple(repairs))
    kind = Kind(case.reply.dimension)
    fact = OpportunityFact(kind, FactState.KNOWN if case.known_value_fact else FactState.UNKNOWN,
                           ("context", "offer", *conflicting_refs) if case.known_value_fact else (),
                           (case.opportunity, case.candidate), conflicting_preference_refs=conflicting_refs)
    vr = Input(Op.INTERPRET_OPPORTUNITY_VALUE, candidate_id, job_id, source_registry=registry,
               candidate_profile=candidate, job_profile=job, hard_facts=hard, opportunity_facts=(fact,))
    presult = interpret(pr, {"links": links})
    vresult = interpret(vr, {"signals": [{"kind": kind.value, "factual_state": fact.state.value,
        "state": case.reply.value, "authority": "explicit", "importance": "core",
        "supporting_refs": list(fact.supporting_refs)}]})
    if any(result.validation_status is ValidationStatus.REJECTED for result in (presult, vresult)):
        return rejected
    interpretation = hiring_interpretation(pr, presult, vr, vresult)
    if semantic_fixture is not None:
        from models.profile_interpretation import SourceEvidence
        from models.semantic_evidence import SemanticSupportRequest
        from services.semantic_evidence_boundary import semantic_requirement_links, signature
        semantic_request = SemanticSupportRequest(pr, tuple(
            SourceEvidence(ref, "career_update", cap.label)
            for cap in candidate.capabilities for ref in cap.evidence_refs
        ))
        raw = {"input_signature": signature(semantic_request),
               "interpreter_version": "adversarial-semantic-fixture-v1", "needs": semantic_fixture}
        interpretation = replace(interpretation, requirement_links=semantic_requirement_links(semantic_request, raw))
    result = build_hiring_case(build_profile_hiring_case_input(
        candidate_profile=candidate, job_profile=job, hard_facts=hard, interpretation=interpretation))
    return dict(classification=result.classification.value, strength=result.hiring_case_strength.value,
                value=result.opportunity.value.value, confidence=result.opportunity.confidence.value,
                states=tuple(item.evidence_state.value for item in result.requirements),
                constraints=tuple((item.evidence_requirement.value, item.constraint_satisfied,
                                   item.constraint_reason_code.value) for item in result.requirements),
                temporal=tuple((item.temporal_requirement.value, item.temporal_applicability.value) for item in result.requirements),
                source_repair=tuple(item.needs_source_repair for item in presult.output_payload.links),
                statuses=statuses, issue_codes=codes)


def evaluate(case):
    actual = observe(case)
    expected = asdict(case.expected)
    dimensions = ("classification", "strength", "value", "states", "confidence")
    mismatches = [key for key in dimensions if actual[key] != expected[key]]
    return {"case_id": case.case_id, "scenario": case.scenario, "expected": expected,
            "actual": actual, "mismatches": mismatches,
            "root_cause": case.taxonomy if mismatches else None}


def run_adversarial():
    rows = [evaluate(case) for case in adversarial_cases()]
    constraint_checks = [row["actual"]["constraints"][index][:2] == ("direct_required", case.expected.states[index] == "proven")
                         for case, row in zip(adversarial_cases(), rows)
                         for index, need in enumerate(case.needs) if need.direct_required]
    return {"version": "adversarial-v1", "status": "frozen_agent_authored_proposals_not_independent_human_gold",
            "total": len(rows),
            "constraint_total": len(constraint_checks), "constraint_matches": sum(constraint_checks),
            "agreements": {key: sum(key not in row["mismatches"] for row in rows)
                           for key in ("classification", "strength", "value", "confidence")},
            "evidence_total": sum(len(row["expected"]["states"]) for row in rows),
            "evidence_matches": sum(sum(a == b for a, b in zip(row["actual"]["states"], row["expected"]["states"])) for row in rows),
            "safe_rejections": sum(row["actual"]["classification"] == "not_evaluated" and not row["mismatches"] for row in rows),
            "taxonomy": dict(Counter(row["root_cause"] for row in rows if row["mismatches"])),
            "cases": rows}


def render_report(result):
    lines = ["# Adversarial v1: frozen offline evaluation", "",
             "Agent-authored proposed judgments, not an independent human-reviewed gold set. Expectations and",
             "controlled replies were initially frozen before execution. AV28 alone was subsequently updated by",
             "explicit human product review: historical support is TRANSFERABLE, not missing. Same-author design",
             "cannot establish statistically blind or real-world AI accuracy. The hardening pass adds explicit",
             "evidence constraints and unresolved preference-source conflicts. Only the authorized AV28 review",
             "changes the previously frozen expectation and controlled semantic relation.", "",
             f"Cases: {result['total']}. Agreements (safe rejection included): {result['agreements']}.",
             f"Evidence: {result['evidence_matches']}/{result['evidence_total']}. Safe rejections: {result['safe_rejections']}.",
             f"Mismatch taxonomy: {result['taxonomy']}.", "",
             f"Explicit evidence constraints: {result['constraint_matches']}/{result['constraint_total']} (AV02).",
             "Rejected cases do not receive a category; they are reported as not_evaluated. Evidence denominators",
             "exclude the two rejection expectations, not silently treat them as successful evidence assessments.", "",
             "| Case | Scenario | Expected category | Observed category | Mismatches | Root cause |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in result["cases"]:
        lines.append(f"| {row['case_id']} | {row['scenario']} | {row['expected']['classification']} | {row['actual']['classification']} | {', '.join(row['mismatches']) or 'none'} | {row['root_cause'] or 'none'} |")
    lines += ["", "## Interpretation", "",
              "Valid refs alone cannot certify semantic relevance or complete coverage. Reuse across unrelated",
              "needs is structurally possible; a semantic evaluator must reject the wrong relationship. Explicit",
              "direct-ownership requirements now use source-backed DIRECT_REQUIRED, independently of IMPORTANT.",
              "AV02 becomes VIABLE without changing TRANSFERABLE evidence. AV30's two explicit, equally current",
              "preference sources now force UNKNOWN; no winner is selected. Semantic support failures remain visible.", "",
              "AV28 now has an explicit source-backed current-procedure requirement, a superseded procedure",
              "version on its historical source, and the reviewed TRANSFERABLE semantic link. Applicability is",
              "NOT_SATISFIED while evidence remains valid. No age threshold, clock or prose matcher is used.",
              "Its expected state and controlled semantic reply changed only under explicit human review; the",
              "other 31 cases and the original 40-case calibration are protected by their existing hashes.", "",
              "Confidence is coarse: HIGH requires all signals known, MEDIUM means mixed, LOW means all unknown.",
              "An additional unknown fact may not lower an already MEDIUM bucket. Marginal confidence and",
              "materiality weighting require a separate reviewed policy; UNKNOWN never becomes negative here.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_adversarial()
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))
