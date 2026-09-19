"""Controlled hypothetical provider replies, authored independently of expected labels.

These fixtures specify links and value signals only. No final category is stored.
Projection of input facts below does not perform semantic matching.
"""
from dataclasses import asdict
import hashlib
import json

from models.hiring_case import OpportunitySignalKind as Kind
from models.profile_interpretation import HardJobFact, JobHardFacts
from models.structured_interpretation import (
    FactState, InterpretationOperation as Op, OpportunityFact,
    RegisteredSourceRef, SourceRefClass as Ref, StructuredInterpretationInput,
)
from services.fixture_structured_interpreter import FixtureStructuredInterpreter, fixture_key
from services.structured_profile_boundary import candidate_snapshot, job_snapshot, hiring_interpretation


# (main assessment, extra assessment, extra importance, value interpretation).
# 'aligned' means the company family and stated current direction agree.
RESPONSES = {
    "HC01a": ("proven", None, None, "aligned"),
    "HC01b": ("evidence_missing", None, None, "aligned"),
    "HC02a": ("proven", None, None, "aligned"),
    "HC02b": ("transferable", None, None, "aligned"),
    "HC03a": ("proven", None, None, "aligned"),
    "HC03b": ("proven", None, None, "aligned"),
    "HC04a": ("proven", "gap", "nice_to_have", "aligned"),
    "HC04b": ("proven", "gap", "core", "aligned"),
    "HC05a": ("proven", None, None, "pay_increase"),
    "HC05b": ("proven", None, None, "pay_loss"),
    "HC06a": ("proven", None, None, "urgent_continuity"),
    "HC06b": ("proven", None, None, "stable_lateral"),
    "HC07a": ("proven", None, None, "aligned"),
    "HC07b": ("evidence_missing", None, None, "aligned"),
    "HC08a": ("proven", None, None, "aligned"),
    "HC08b": ("proven", None, None, "aligned"),
    "HC09a": ("proven", None, None, "aligned"),
    "HC09b": ("proven", None, None, "avoided_content"),
    "HC10a": ("proven", None, None, "aligned"),
    "HC10b": ("proven", None, None, "aligned"),
    "HC11a": ("proven", "gap", "core", "avoided_content"),
    "HC11b": ("proven", "gap", "core", "avoided_content"),
    "HC12a": ("proven", None, None, "aligned"),
    "HC12b": ("evidence_missing", None, None, "aligned"),
    "HC13a": ("proven", None, None, "aligned"),
    "HC13b": ("proven", None, None, "aligned"),
    "HC14a": ("proven", None, None, "aligned"),
    "HC14b": ("proven", None, None, "different_direction"),
    "HC15a": ("proven", "proven", "important", "aligned"),
    "HC15b": ("proven", "transferable", "important", "aligned"),
    "HC16a": ("proven", None, None, "aligned"),
    "HC16b": ("proven", None, None, "aligned"),
    "HC17a": ("proven", None, None, "aligned"),
    "HC17b": ("proven", None, None, "aligned"),
    "HC18a": ("proven", None, None, "first_lead_role"),
    "HC18b": ("proven", None, None, "down_level"),
    "HC19a": ("proven", None, None, "lateral_uncertain"),
    "HC19b": ("proven", None, None, "valued_pay_bridge"),
    "HC20a": ("proven", None, None, "aligned"),
    "HC20b": ("proven", None, None, "commute_unknown"),
}

# Controlled outputs, not a keyword interpreter. Omitted dimensions explicitly abstain.
VALUE_RESPONSES = {
    "aligned": (("career_direction", "positive", "core"),),
    "pay_increase": (("career_direction", "positive", "core"), ("compensation", "positive", "important")),
    "pay_loss": (("career_direction", "positive", "core"), ("compensation", "negative", "core")),
    "urgent_continuity": (("objective_timing", "positive", "core"),),
    "stable_lateral": (("objective_timing", "negative", "core"),),
    "avoided_content": (("role_content", "negative", "core"),),
    "different_direction": (("career_direction", "negative", "important"),),
    "first_lead_role": (("seniority_progression", "positive", "core"),),
    "down_level": (("seniority_progression", "negative", "core"),),
    "lateral_uncertain": (),
    "valued_pay_bridge": (("compensation", "positive", "core"), ("strategic_value", "positive", "important")),
    "commute_unknown": (("career_direction", "positive", "core"),),
}


def signed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# Pinned facts only: editing reference judgments does not change this manifest.
SOURCE_SIGNATURES = {
    "HC01a": "c2b3358a3200ab6ccfa6b668928189515a960e3c4eb482c624927f807d43d054",
    "HC01b": "7a7f79ac8f9564de51c7d42038cbce91ff4b2366a451f5dfa4b6850d081194f2",
    "HC02a": "c2b3358a3200ab6ccfa6b668928189515a960e3c4eb482c624927f807d43d054",
    "HC02b": "151012cc4642c92fa5db7fb1b19f312477caa12970a4a5c2aa93ff0ef581a65e",
    "HC03a": "c2b3358a3200ab6ccfa6b668928189515a960e3c4eb482c624927f807d43d054",
    "HC03b": "e32a878898967e81d8d01eff41ef77b4006e4c50b83e379ee7d5bd018dbe0018",
    "HC04a": "b9e59cbacb3c9f490c949aaa9286302c6c11cc7357cf8ee017d6741e81881b6a",
    "HC04b": "59d62cab2b1c9eaae71618115d7478f11b187ae8abe61107179e9596cc32d55f",
    "HC05a": "906d9833959019b467336dc11c10ab793d2964d315bed708118dbe31f528e934",
    "HC05b": "78dbc5cdae1e4ac26db6d4bf87753e7aacf569e6b41bcb868b84f1d9c72de60a",
    "HC06a": "24478077d94b2eed3420c9b3f1750c5eb5ef79f3d2d48566de6d43554c60ced0",
    "HC06b": "2852c6a7541271273199702eba65c236624222923ffe8e4f38eff8491a5fd50c",
    "HC07a": "9a2f9d1b81c11fde46cbcd84f01240d8b3b04ff61aee00e69bbd8511c21211de",
    "HC07b": "d0b6003c99291f21855f2f2c5f96000a8f59793cfd8d646ba09c9fe95400ceba",
    "HC08a": "623adcb44f21a6192aa6b029af73764309a7ccefa5cb54c691ff4de264e755b0",
    "HC08b": "c92b5b08abced61010cadadd114f586c0220ba391ef546812e79c1524c2aa774",
    "HC09a": "623adcb44f21a6192aa6b029af73764309a7ccefa5cb54c691ff4de264e755b0",
    "HC09b": "db3d7c2f38dac7147bdf12c5fbba71afdeee434d89020e08b0b9cf9b4632c681",
    "HC10a": "4945621ef132e1fc5acef5e870e961ba978ca4a0c8ea6ea9832984c97c63b142",
    "HC10b": "6561a23237885129d8b2502b0c9322d9cdb0e029507d128f17dfcd1ee92b91e8",
    "HC11a": "1c446930ac33656926c1dd5a4dfee20ae571cd16040956de5e1c805989679260",
    "HC11b": "b9bc29325e10be267c32113cefcaea7ec43a0f3fa29b7bc9e1ded6459c81ede4",
    "HC12a": "69a070b0d79ad3c255dcc994977e6f6cab60b80b15b4268e622c6fd7eef5bc3e",
    "HC12b": "9c08fbb5ba52ffd6d9c1fe47a71bc7f4ce43b36a213092ada032b2c14fb11d6c",
    "HC13a": "66c09735228ccf08ec24dc2126e036fc85a0459e81909a9633dab283fd8cf206",
    "HC13b": "7d187cfa48bf18c4ae14daa88ccb6dddfcaddaa47eadfdfcbf45e1f89bdbf65c",
    "HC14a": "66c09735228ccf08ec24dc2126e036fc85a0459e81909a9633dab283fd8cf206",
    "HC14b": "6e6cabdc02b77e3bfffaf00a13e2cf16c808d3595765fef0e6588231fa9f3c9e",
    "HC15a": "2e58c428c91288c0050045386e2fb562964668c6adb07f3c9070eedb375fa3d8",
    "HC15b": "dcc50e2d6462b59607560e5fb860b3f4e112e7e1fc439411784f00b808fe2126",
    "HC16a": "1f78afe8ce7ccdefb98d3ee1e4b451b77da93a0954f4e3b37c791891e956dcaa",
    "HC16b": "89df4d84a75320e51383750bac99777a2b530dcfbbe527f0f21122ca9a47bf3b",
    "HC17a": "204c5383909f67c537c8da36f34ec73235931c110c185845156acc782ed6aa2d",
    "HC17b": "c11320554ce32cffa3ca219ba95709fa56e6b8ed43e27eb4854c4cee9d37a8f7",
    "HC18a": "4c33c55024c86c47f7289fded99056942a39c285885dd0cc37c049e0020a4aa0",
    "HC18b": "657e8026b2fb3c377a6fe7420f0e21853baad1c547f6365dc212efa731802684",
    "HC19a": "6d2ca356bf6a25361deb10d3261383cfc04afad50ebd7c7f712e1c1a87d661f4",
    "HC19b": "1433f77bb24b62887b9feb90a3e53923a26e6d32539252b0f6e210beab7b3f13",
    "HC20a": "790c91a219c5ffb7a1cfe91d0841fecca78bde89660e29d8fe5dfd41dee933d0",
    "HC20b": "ead16f421772ce574ccbc36fb775431b8e0263d419aa49d412e41963b9775fb5"
}


def fixture_requests(case_id, facts, candidate_id, job_id):
    if signed(asdict(facts)) != SOURCE_SIGNATURES.get(case_id):
        raise ValueError("fixture_unavailable")
    main, extra, extra_importance, value_key = RESPONSES[case_id]
    projection = asdict(facts.candidate)
    projection["objectives_preferences"] = asdict(facts.opportunity)
    registry, caps, links, needs = [], [], [], []
    hard_records = []
    absent = []
    capability_by_key = {item.key: item for item in facts.candidate.capabilities}
    for index, need in enumerate(facts.company.needs):
        proof = capability_by_key[need.key].proof
        state = main if index == 0 else extra
        refs = []
        # Source availability is a hard fixture fact, independent of returned interpretation.
        if proof.kind in {"direct", "transferable"} and proof.source_available:
            refs = [f"evidence:{need.key}"]
            registry.append(RegisteredSourceRef(refs[0], Ref.CANDIDATE_EVIDENCE, candidate_id,
                                                "professional_experience", usable_evidence=True))
        if proof.kind == "confirmed_gap":
            absent.append(need.key)
            registry.append(RegisteredSourceRef(f"absence:{need.key}", Ref.CAREER_MEMORY_SOURCE,
                                                candidate_id, "career_update", confirmed_absence_for=(need.key,)))
        if state in {"proven", "transferable"}:
            caps.append({"capability_id": need.key, "label": proof.wording, "evidence_refs": refs,
                         "transferable": state == "transferable"})
        links.append({
            "need_id": need.key, "candidate_capability_id": need.key if refs else None,
            "assessment": state, "evidence_refs": refs,
            "confidence": "high" if refs else "unknown",
            "reason_code": {"proven": "direct_support", "transferable": "adjacent_support",
                            "evidence_missing": "needs_example", "gap": "confirmed_absence"}[state],
            "needs_evidence": state == "evidence_missing",
            "evidence_question_hint": need.question if state == "evidence_missing" else "",
        })
        fact_id = f"job-need:{need.key}"
        hard_records.append(HardJobFact(fact_id, need.parsed_slot or "stated_requirement", need.text, f"job:{job_id}:{need.key}"))
        needs.append({"need_id": need.key, "label": need.text, "importance": "core" if index == 0 else extra_importance,
                      "authority": "explicit", "hard_fact_refs": [fact_id]})
    if facts.company.eligibility_blocker:
        hard_records.append(HardJobFact("eligibility", "eligibility", facts.company.eligibility_blocker,
                                       f"job:{job_id}:eligibility", hard_blocker=True))
    # Source dimensions retain the supplied facts, not inferred sentiment.
    opp = facts.opportunity
    dimension_facts = {
        Kind.COMPENSATION: (opp.compensation.annual_offer is not None and opp.compensation.annual_current is not None,
                            json.dumps(asdict(opp.compensation), sort_keys=True)),
        Kind.CAREER_DIRECTION: (True, opp.career_direction + " | " + opp.desired_family + " | " + facts.company.family),
        Kind.GROWTH: (True, opp.growth),
        Kind.SENIORITY_PROGRESSION: (True, facts.candidate.context.scope + " | " + opp.progression),
        Kind.ROLE_CONTENT: (True, opp.role_content),
        Kind.WORK_MODE_LOCATION: (False, opp.location + " | " + opp.work_mode),
        Kind.STRATEGIC_VALUE: (True, opp.career_direction + " | " + opp.compensation.tradeoff),
        Kind.TRADE_OFF: (True, opp.tradeoffs),
        Kind.OBJECTIVE_TIMING: (True, opp.timing),
    }
    opportunity_facts = []
    for kind, (known, text) in dimension_facts.items():
        refs = (f"context:{kind.value}", f"job-context:{kind.value}") if known else ()
        if known:
            registry.append(RegisteredSourceRef(refs[0], Ref.CAREER_MEMORY_SOURCE, candidate_id, "candidate_context"))
            job_context = {
                "expected_work": facts.company.expected_work,
                "family": facts.company.family,
                "seniority": facts.company.seniority_context,
                "annual_offer": opp.compensation.annual_offer,
                "work_mode": opp.work_mode,
                "location": opp.location,
            }
            hard_records.append(HardJobFact(refs[1], kind.value, json.dumps(job_context, sort_keys=True),
                                           f"job:{job_id}:context"))
        opportunity_facts.append(OpportunityFact(kind, FactState.KNOWN if known else FactState.UNKNOWN, refs, (text,)))
    hard = JobHardFacts(job_id, signed([asdict(item) for item in hard_records]), tuple(hard_records))
    registry.extend(RegisteredSourceRef(item.fact_id, Ref.JOB_HARD_FACT, job_id, "job_description") for item in hard_records)
    registry = tuple(registry)
    candidate_request = StructuredInterpretationInput(
        Op.BUILD_CANDIDATE_PROFILE, candidate_id, job_id, signed(projection), projection, registry, hard_facts=hard,
    )
    candidate_response = {
        "capabilities": caps,
        "checkpoint": {"current_position": facts.candidate.context.scope},
        "confirmed_gaps": absent,
        "objectives": [opp.career_direction], "preferences": [opp.role_content],
        "seniority": facts.candidate.context.level, "responsibility_scope": facts.candidate.context.scope,
    }
    job_request = StructuredInterpretationInput(Op.BUILD_JOB_PROFILE, candidate_id, job_id,
                                                source_registry=registry, hard_facts=hard)
    job_response = {"needs": needs, "problem_to_solve": facts.company.expected_work}
    clock = lambda: "2026-01-01T00:00:00+00:00"
    interpreter = FixtureStructuredInterpreter({fixture_key(candidate_request): candidate_response,
                                                fixture_key(job_request): job_response}, clock=clock)
    cr, jr = interpreter.interpret(candidate_request), interpreter.interpret(job_request)
    candidate, job = candidate_snapshot(candidate_request, cr), job_snapshot(job_request, jr)
    pair_request = StructuredInterpretationInput(
        Op.ANALYZE_HIRING_CASE, candidate_id, job_id, source_registry=registry,
        candidate_profile=candidate, job_profile=job, hard_facts=hard,
        seniority_context_mismatch=facts.candidate.context.severe_mismatch,
        source_repair_need_ids=tuple(item.key for item in facts.candidate.capabilities
                                    if item.proof.example and not item.proof.source_available),
    )
    value_request = StructuredInterpretationInput(
        Op.INTERPRET_OPPORTUNITY_VALUE, candidate_id, job_id, source_registry=registry,
        candidate_profile=candidate, job_profile=job, hard_facts=hard, opportunity_facts=tuple(opportunity_facts),
    )
    selected = {kind: (state, importance) for kind, state, importance in VALUE_RESPONSES[value_key]}
    signals = []
    for fact in opportunity_facts:
        state, importance = selected.get(fact.kind.value, ("unknown", "important"))
        signals.append({
            "kind": fact.kind.value, "factual_state": fact.state.value, "state": state,
            "authority": "strongly_implied" if state != "unknown" else "unknown",
            "supporting_refs": list(fact.supporting_refs) if state != "unknown" else [],
            "importance": importance,
        })
    interpreter = FixtureStructuredInterpreter({fixture_key(pair_request): {"links": links},
                                                fixture_key(value_request): {"signals": signals}}, clock=clock)
    pr, vr = interpreter.interpret(pair_request), interpreter.interpret(value_request)
    interpretation = hiring_interpretation(pair_request, pr, value_request, vr)
    return candidate, job, hard, interpretation, (cr, jr, pr, vr)
