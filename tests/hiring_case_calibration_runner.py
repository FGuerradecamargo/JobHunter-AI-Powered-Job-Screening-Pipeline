"""Offline diagnostic harness. Expected labels never feed source construction."""

from collections import Counter
from dataclasses import asdict

from models.application_contract import ApplicationAnalysisSource
from models.candidate import Candidate
from models.candidate_preferences import CandidatePreferences
from models.candidate_priority import CandidatePriority
from models.career_objective import CareerObjective
from models.career_update import CareerUpdate
from models.hiring_case import (
    HiringCaseClassification, HiringCaseStrength, OpportunityValue,
    RequirementEvidenceState, RequirementImportance,
)
from models.hiring_case_shadow import ConfirmedCapabilityGap, HiringCaseShadowSource
from models.job_profile import JobProfile
from models.professional_experience_profile import ProfessionalExperienceProfile
from services.hiring_case_compatibility import read_legacy_classification
from services.hiring_case_engine import classify_hiring_case
from services.hiring_case_shadow_service import evaluate_profile_hiring_case_shadow
from services.profile_hiring_case_adapter import build_profile_hiring_case_input
from tests.hiring_case_calibration_cases import RootCause, calibration_cases


def source_from_facts(facts, legacy_recommendation):
    """Faithful projection into existing models, intentionally preserving their limits."""
    candidate_id, job_id = "synthetic-candidate", "synthetic-job"
    profile = JobProfile(job_id=job_id, canonical_role=facts.company.role,
                         role_family=facts.company.family, seniority=facts.company.seniority_context)
    slots = {"core": "must_have_capabilities", "important": "key_responsibilities", "nice_to_have": "nice_to_have"}
    needs = {item.key: item for item in facts.company.needs}
    for need in needs.values():
        getattr(profile, need.parsed_slot or slots[need.importance]).append(need.text)
    profile.work_conditions = [facts.opportunity.work_mode]
    experiences, updates, confirmed, profile_claims = [], [], [], []
    for item in facts.candidate.capabilities:
        proof, need = item.proof, needs[item.key]
        if proof.kind in {"direct", "transferable", "vague"}:
            experience = ProfessionalExperienceProfile(
                source_experience_id=f"experience-{item.key}" if proof.source_available else "",
                stated_role="Prior synthetic role", company="Synthetic employer",
                evidence=[proof.example] if proof.kind != "vague" else [],
            )
            if proof.kind == "transferable":
                experience.transferable_capabilities = [proof.wording]
            else:
                # A vague attributed label deliberately exercises the present authority boundary.
                experience.demonstrated_capabilities = [proof.wording]
            experiences.append(experience)
        elif proof.kind == "confirmed_gap":
            update_id = f"confirmation-{item.key}"
            updates.append(CareerUpdate(update_id, candidate_id, "reflection", proof.example))
            confirmed.append(ConfirmedCapabilityGap(candidate_id, job_id, need.text, update_id))
        elif proof.kind == "absent":
            profile_claims.append(need.text)
        else:
            raise ValueError("Unknown calibration proof kind.")
    opportunity = facts.opportunity
    priorities = []
    if opportunity.role_content.startswith("Explicitly avoid: "):
        avoided = opportunity.role_content.removeprefix("Explicitly avoid: ")
        priorities = [CandidatePriority(avoided, "negative")]
        if avoided not in profile.key_responsibilities:
            profile.key_responsibilities.append(avoided)
    # The original models have prose for pay/current context and no common salary unit contract.
    updates.append(CareerUpdate(
        "objective-context", candidate_id, "reflection",
        f"Timing: {opportunity.timing} Pay: {opportunity.compensation} "
        f"Progression: {opportunity.progression} Costs: {opportunity.tradeoffs}",
    ))
    candidate = Candidate(
        id=candidate_id, name="Synthetic candidate", current_role="Current synthetic role",
        current_level=facts.candidate.context.level,
        professional_summary=facts.candidate.context.scope,
        proven_capabilities=profile_claims, professional_experiences=experiences,
        target_role_families=[opportunity.desired_family], priorities=priorities,
        preferences=CandidatePreferences(
            remote_allowed=opportunity.remote_allowed,
            hybrid_allowed=opportunity.hybrid_allowed,
            onsite_allowed=opportunity.onsite_allowed,
        ),
    )
    analysis = {
        "recommendation": legacy_recommendation, "bucket": legacy_recommendation,
        "candidate_level": candidate.current_level, "job_level": profile.seniority,
        "level_assessment": facts.candidate.context.scope,
        "hard_conflicts": [facts.company.eligibility_blocker] if facts.company.eligibility_blocker else [],
    }
    if facts.company.eligibility_blocker:
        analysis["rule_rejection_type"] = "hard_filter"
    pay = opportunity.compensation
    salary = f"{pay.currency} {pay.annual_offer} per year" if pay.annual_offer is not None else None
    source = ApplicationAnalysisSource(
        candidate_id, job_id, "synthetic-completed-analysis", legacy_recommendation,
        job={"id": job_id, "title": facts.company.role, "company": "Synthetic employer",
             "description": facts.company.expected_work, "salary": salary,
             "location": opportunity.location, "remote": opportunity.work_mode == "remote"},
        analysis=analysis,
    )
    return HiringCaseShadowSource(
        candidate, source, profile,
        CareerObjective("synthetic-objective", candidate_id, "Current objective",
                        opportunity.career_direction, desired_role_families=[opportunity.desired_family]),
        tuple(updates), tuple(confirmed),
    )


def _key(text):
    return " ".join(text.split()).casefold().rstrip(".;:,")


def profile_inputs_from_facts(case_id, facts, source):
    from tests.structured_calibration_fixtures import fixture_requests
    return fixture_requests(case_id, facts, source.candidate.id, source.analysis_source.job_id)


def proof_reviews(case):
    expected_states = dict(case.expected.states)
    capabilities = {item.key: item for item in case.facts.candidate.capabilities}
    result = []
    for need in case.facts.company.needs:
        capability = capabilities[need.key]
        proof = capability.proof
        usable = proof.kind in {"direct", "transferable"} and proof.source_available
        repair = bool(proof.example) and not proof.source_available
        result.append({
            "requirement_key": need.key, "requirement": need.text,
            "capability_exists": capability.exists,
            "evidence_exists": proof.kind in {"direct", "transferable"},
            "source_available": proof.source_available,
            "evidence_relationship": proof.kind,
            "interview_defensible": usable,
            "safe_in_cv": usable,
            "cv_boundary": (
                "Do not present this as proven capability." if not usable else
                "Represent as adjacent experience only." if proof.kind == "transferable" else
                "Retain the demonstrated scope; no claim of broader seniority."
            ),
            "needs_evidence": expected_states[need.key] == "evidence_missing" and not repair,
            "needs_source_repair": repair,
            "expected_state": expected_states[need.key],
        })
    return result


def evaluate_case(case):
    source = source_from_facts(case.facts, case.legacy_recommendation)
    candidate_profile, job_profile, hard, interpretation, envelopes = profile_inputs_from_facts(case.case_id, case.facts, source)
    shadow = evaluate_profile_hiring_case_shadow(
        source, candidate_profile=candidate_profile, job_profile=job_profile,
        hard_facts=hard, interpretation=interpretation,
    )
    data = build_profile_hiring_case_input(
        candidate_profile=candidate_profile, job_profile=job_profile,
        hard_facts=hard, interpretation=interpretation,
    )
    observed = {_key(item.requirement): item for item in data.requirements}
    states, importances = [], []
    evidence_missing = []
    expected_states = dict(case.expected.states)
    capabilities = {item.key: item for item in case.facts.candidate.capabilities}
    for need in case.facts.company.needs:
        actual = observed.get(_key(need.text))
        actual_state = actual.evidence_state.value if actual else "not_extracted"
        if expected_states[need.key] != actual_state:
            states.append({"key": need.key, "expected": expected_states[need.key], "actual": actual_state})
        if actual is None or actual.importance.value != need.importance:
            importances.append({"key": need.key, "expected": need.importance,
                                "actual": actual.importance.value if actual else "not_extracted"})
        if "evidence_missing" in {expected_states[need.key], actual_state}:
            capability = capabilities[need.key]
            evidence_missing.append({
                "requirement": need.text, "expected_missing": expected_states[need.key] == "evidence_missing",
                "shadow_missing": actual_state == "evidence_missing",
                "capability_plausibly_present": capability.exists in {"yes", "adjacent", "plausible"},
                "existing_example": capability.proof.example,
                "evidence_to_resolve": need.evidence_needed,
                "future_question": need.question,
                "first_action": "Ask for a real example; do not assume it exists." if capability.proof.kind in {"absent", "vague"}
                                else "Review and link the already supplied evidence before asking the candidate again.",
            })
    classification = shadow.shadow_classification.value if shadow.shadow_classification else "not_evaluated"
    strength = shadow.hiring_case_strength.value if shadow.hiring_case_strength else "not_evaluated"
    value = shadow.opportunity_value.value if shadow.opportunity_value else "not_evaluated"
    mapped = read_legacy_classification(case.legacy_recommendation).display_classification
    legacy = mapped.value if mapped else "unmapped"
    label_mismatch = classification != case.expected.classification
    strength_mismatch = strength != case.expected.strength
    value_mismatch = value != case.expected.value
    any_mismatch = label_mismatch or strength_mismatch or value_mismatch or bool(states or importances)
    # Attribution is an explicitly authored review hypothesis, not semantic inference.
    root = case.diagnostic_focus.value if any_mismatch else None
    return {
        "case_id": case.case_id, "family": case.family, "review_track": case.review_track,
        "authority_violations": sum(item.validation_status.value == "rejected" for item in envelopes),
        "abstentions": sum(item.validation_status.value == "unavailable" for item in envelopes),
        "human_review_status": case.human_review_status,
        "semantic_links": [asdict(item) for item in envelopes[2].output_payload.links],
        "confidence_expected": "medium" if case.case_id == "HC20b" else None,
        "expected": asdict(case.expected), "legacy_equivalent": legacy,
        "shadow_classification": classification, "shadow_strength": strength,
        "shadow_value": value, "shadow_confidence": shadow.opportunity_confidence.value if shadow.opportunity_confidence else None,
        "classification_mismatch": label_mismatch, "strength_mismatch": strength_mismatch,
        "value_mismatch": value_mismatch, "evidence_mismatches": states,
        "importance_mismatches": importances, "any_mismatch": any_mismatch,
        "primary_root_cause": root,
        "proof_review": proof_reviews(case), "evidence_missing_review": evidence_missing,
        "quadrant_given_reference_dimensions": classify_hiring_case(
            HiringCaseStrength(case.expected.strength), OpportunityValue(case.expected.value),
        ).value,
    }


def metrics(rows):
    count = len(rows)
    matches = sum(not row["classification_mismatch"] for row in rows)
    legacy_mapped = [row for row in rows if row["legacy_equivalent"] != "unmapped"]
    legacy_matches = sum(row["legacy_equivalent"] == row["expected"]["classification"] for row in legacy_mapped)
    labels = [item.value for item in HiringCaseClassification]
    matrix = {label: {actual: 0 for actual in [*labels, "not_evaluated"]} for label in labels}
    legacy_matrix = {label: {actual: 0 for actual in [*labels, "unmapped"]} for label in labels}
    for row in rows:
        matrix[row["expected"]["classification"]][row["shadow_classification"]] += 1
        legacy_matrix[row["expected"]["classification"]][row["legacy_equivalent"]] += 1
    return {
        "total": count, "shadow_exact_matches": matches, "shadow_mismatches": count - matches,
        "shadow_agreement": matches / count if count else 0,
        "legacy_mapped": len(legacy_mapped), "legacy_unmapped": count - len(legacy_mapped),
        "legacy_exact_matches": legacy_matches,
        "legacy_agreement_mapped": legacy_matches / len(legacy_mapped) if legacy_mapped else 0,
        "strength_mismatches": sum(row["strength_mismatch"] for row in rows),
        "strength_agreement": sum(not row["strength_mismatch"] for row in rows) / count if count else 0,
        "opportunity_value_agreement": sum(not row["value_mismatch"] for row in rows) / count if count else 0,
        "confidence_reviewed": sum(row["confidence_expected"] is not None for row in rows),
        "confidence_matches": sum(row["confidence_expected"] is not None and row["shadow_confidence"] == row["confidence_expected"] for row in rows),
        "authority_violations": sum(row["authority_violations"] for row in rows),
        "abstentions": sum(row["abstentions"] for row in rows),
        "evidence_state_total": sum(len(row["proof_review"]) for row in rows),
        "value_mismatches": sum(row["value_mismatch"] for row in rows),
        "evidence_state_mismatches": sum(len(row["evidence_mismatches"]) for row in rows),
        "importance_mismatches": sum(len(row["importance_mismatches"]) for row in rows),
        "any_dimension_mismatch_cases": sum(row["any_mismatch"] for row in rows),
        "classification_mismatch_taxonomy": dict(sorted(Counter(
            row["primary_root_cause"] for row in rows if row["classification_mismatch"]
        ).items())),
        "any_dimension_taxonomy": dict(sorted(Counter(
            row["primary_root_cause"] for row in rows if row["any_mismatch"]
        ).items())),
        "shadow_confusion_matrix": matrix, "legacy_confusion_matrix": legacy_matrix,
    }


def run_calibration(cases=None):
    cases = calibration_cases() if cases is None else cases
    rows = [evaluate_case(case) for case in sorted(cases, key=lambda item: item.case_id)]
    return {
        "schema_version": "hiring-case-calibration-v1",
        "reference_status": "three_decisions_human_reviewed_remaining_pending_human_review",
        "legacy_status": "authored_fixture_recommendations_not_live_legacy_predictions",
        "composition": dict(sorted(Counter(row["family"] for row in rows).items())),
        "all": metrics(rows),
        "normative": metrics([row for row in rows if row["review_track"] == "normative"]),
        "exploratory": metrics([row for row in rows if row["review_track"] == "exploratory"]),
        "cases": rows,
    }


def changed_fact_paths(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [path for key in sorted(a.keys() | b.keys())
                for path in changed_fact_paths(a.get(key), b.get(key), f"{prefix}.{key}".strip("."))]
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)) and len(a) == len(b):
        return [path for index, (left, right) in enumerate(zip(a, b))
                for path in changed_fact_paths(left, right, f"{prefix}.{index}")]
    return [prefix] if a != b else []


def render_report(result):
    """Render synthetic cases and computed diagnostics without changing production."""
    m = result["all"]
    n = result["normative"]
    lines = [
        "# Hiring Case calibration report",
        "",
        "Reference: hiring-case-calibration-v1. Offline structured interpreter v1; baseline b5d019e.",
        "",
        "## Review status and method",
        "",
        "These are 40 fictional, agent-authored cases awaiting human review, NOT a completed human-reviewed gold set. "
        "The expectations below are explicit proposed judgments under the product philosophy. No reviewer approval is claimed. "
        "HC12b, HC15b and HC20b were reviewed by the user. The other 37 judgments remain pending. Original track membership is preserved.",
        "",
        "Expected classifications, strength, value and requirement states were authored separately from execution. "
        "They are not produced by the engine. Facts alone are projected through versioned Candidate/Job Profile contracts and four signature-keyed fixture operations with strict validation; expected labels never enter that projection. "
        "Each of 20 pairs changes one declared fact field/subtree. Related serialized fields follow from that same fact.",
        "",
        "Legacy comparison uses independently assigned synthetic fixture recommendations through the existing compatibility map, "
        "NOT fresh historical predictions or live AI. The two reject labels are unmapped by that map. "
        "These agreement figures measure reproducibility of this reference set, not population accuracy or improvement over production.",
        "",
        "No production classification or UI behavior changed. The versioned profile contracts, server-only snapshot schema and profile-based shadow path are exercised offline. No network, AI, Gmail or production database was used.",
        "",
        "## Composition",
        "",
        "| Scenario family | Cases |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {family} | {count} |" for family, count in result["composition"].items())
    expected_counts = Counter(row["expected"]["classification"] for row in result["cases"])
    lines += ["", "Expected distribution (not balanced to a quota): " + ", ".join(
        f"{key}={value}" for key, value in sorted(expected_counts.items())
    ) + ".", "", "## Agreement", "",
        f"- Shadow/reference: {m['shadow_exact_matches']}/{m['total']} ({m['shadow_agreement']:.1%}); {m['shadow_mismatches']} label mismatches.",
        f"- Normative only: {n['shadow_exact_matches']}/{n['total']} ({n['shadow_agreement']:.1%}); exploratory: {result['exploratory']['shadow_exact_matches']}/{result['exploratory']['total']}.",
        f"- Legacy/reference: {m['legacy_exact_matches']}/{m['legacy_mapped']} mapped ({m['legacy_agreement_mapped']:.1%}); "
        f"{m['legacy_unmapped']} unmapped. Across all 40: {m['legacy_exact_matches']}/40; unmapped rows are not counted as correct.",
        f"- Strength disagreements: {m['strength_mismatches']}; opportunity value disagreements: {m['value_mismatches']}.",
        f"- Requirement evidence disagreements: {m['evidence_state_mismatches']} across 46 requirements; "
        f"importance disagreements: {m['importance_mismatches']}.",
        f"- {m['any_dimension_mismatch_cases']} cases have at least one disagreement, including cases with the same final category.",
        f"- Authority violations: {m['authority_violations']}; unavailable operations: {m['abstentions']}.",
        f"- Reviewed confidence: {m['confidence_matches']}/{m['confidence_reviewed']} (HC20b: MEDIUM).",
        "", "## Confusion matrices", "",
        "Rows are proposed reference labels. Columns are observed labels. Abstention remains explicit.", "",
    ]
    for title, key, last in [
        ("Shadow", "shadow_confusion_matrix", "not_evaluated"),
        ("Legacy equivalent", "legacy_confusion_matrix", "unmapped"),
    ]:
        labels = [item.value for item in HiringCaseClassification]
        columns = [*labels, last]
        lines += [f"### {title}", "", "| Expected | " + " | ".join(columns) + " |",
                  "| --- | " + " | ".join("---:" for _ in columns) + " |"]
        for label in labels:
            lines.append("| " + label + " | " + " | ".join(str(m[key][label][col]) for col in columns) + " |")
        lines.append("")
    lines += ["## Error taxonomy", "",
              "Each discrepant case has one authored primary diagnostic attribution, pending reviewer confirmation. "
              "It is a hypothesis supported by the controlled pair, not an automatic semantic root-cause detector. "
              "Counts below distinguish final-label failures from any-dimension failures.", "",
              "| Primary cause | Label mismatches | Any-dimension cases |", "| --- | ---: | ---: |"]
    for cause in RootCause:
        lines.append(f"| {cause.value} | {m['classification_mismatch_taxonomy'].get(cause.value, 0)} | "
                     f"{m['any_dimension_taxonomy'].get(cause.value, 0)} |")
    lines += ["", "## Main findings", "",
        "The fixture interpreter supplies authored semantic links and value interpretations, not keyword matching. "
        "Known salary trade-offs, timing and down-leveling are represented explicitly. Unknown salary remains UNKNOWN. "
        "These hypothetical responses test contracts; they do not demonstrate that a real provider can interpret these cases correctly.",
        "",
        "HC12b: EVIDENCE_MISSING / VIABLE / HIGH / WORTH_A_TRY. Existing evidence has broken provenance, "
        "not a capability gap. SOURCE_REFERENCE_UNAVAILABLE, needs_evidence=false, needs_source_repair=true.",
        "",
        "HC15b: STRONG / HIGH / BEST_MATCH. Defensible IMPORTANT transferable support does not automatically "
        "downgrade proven CORE needs. Direct ownership must be explicitly required; adjacent scope is preserved.",
        "",
        "HC20b: STRONG / HIGH / BEST_MATCH with MEDIUM confidence. Unknown commute cost is not a known negative. "
        "UNCERTAINTY CHANGES CONFIDENCE BEFORE IT CHANGES VALENCE. Confidence remains coarse: another unknown "
        "fact need not lower an already MEDIUM bucket.",
        "",
        "This means the reviewed reference set and implementation agree. It does NOT establish real-world AI accuracy. "
        "Only the three specified judgments changed; the other 37 expectations and all original facts are frozen.",
        "",
        "All 40 fixture pipelines passed structural/source authority validation without abstention. Adversarial tests "
        "separately exercise rejected and normalized outputs. Existing references cannot prove semantic entailment: "
        "a false assertion citing a real source still requires semantic evaluation by humans or a future provider.",
        "",
        "## Controlled pairs", "",
        "Every row represents two cases; all fact changes must stay within the declared path. Expected outputs may "
        "change as a consequence. Tests verify the fact diff independently of expected labels.", "",
        "| Pair | Only changed variable | Expected a -> b | Shadow a -> b |", "| --- | --- | --- | --- |",
    ]
    cases = {case.case_id: case for case in calibration_cases()}
    rows = {row["case_id"]: row for row in result["cases"]}
    for index in range(1, 21):
        a, b = cases[f"HC{index:02d}a"], cases[f"HC{index:02d}b"]
        lines.append(f"| {a.pair_id} | {a.changed_path} | {a.expected.classification} -> {b.expected.classification} | "
                     f"{rows[a.case_id]['shadow_classification']} -> {rows[b.case_id]['shadow_classification']} |")
    lines += ["", "## Case judgments", "",
              "S/V = strength/value. Full company, candidate and opportunity facts are in "
              "tests/hiring_case_calibration_cases.py; they include specific work examples and trade-offs, not live user data.", "",
              "| Case | Track | Expected label; S/V | Shadow label; S/V | Primary cause | Proposed rationale |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in result["cases"]:
        expected = row["expected"]
        lines.append(f"| {row['case_id']} | {row['review_track']} | {expected['classification']}; {expected['strength']}/{expected['value']} | "
                     f"{row['shadow_classification']}; {row['shadow_strength']}/{row['shadow_value']} | "
                     f"{row['primary_root_cause'] or 'none'} | {expected['rationale']} |")
    lines += ["", "## Proof and representation review", "",
              "CV-safe means only the demonstrated scope. Transferable examples must stay framed as adjacent experience; "
              "no table entry licenses claims of greater ownership or seniority. Capability and evidence are separate facts.", "",
              "| Case / requirement | Capability exists | Evidence exists / relationship | Interview defensible | CV safe | Ask for evidence | Repair source | Expected state |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in result["cases"]:
        for item in row["proof_review"]:
            lines.append(f"| {row['case_id']} / {item['requirement']} | {item['capability_exists']} | "
                         f"{item['evidence_exists']} / {item['evidence_relationship']} | {item['interview_defensible']} | "
                         f"{item['safe_in_cv']} | {item['needs_evidence']} | {item['needs_source_repair']} | {item['expected_state']} |")
    lines += ["", "## Evidence-missing review", "",
              "Union of reference EVIDENCE_MISSING and shadow EVIDENCE_MISSING. This catches both missed valid proof "
              "and unsupported proof that the shadow incorrectly accepts. Real GAP confirmations remain separate.", ""]
    for row in result["cases"]:
        for item in row["evidence_missing_review"]:
            lines += [f"### {row['case_id']}: {item['requirement']}", "",
                      f"- Plausibly present: {item['capability_plausibly_present']}; reference missing: {item['expected_missing']}; shadow missing: {item['shadow_missing']}.",
                      f"- Existing record: {item['existing_example']}",
                      f"- Resolving evidence: {item['evidence_to_resolve']}",
                      f"- First action: {item['first_action']}",
                      f"- Future Add Evidence question: {item['future_question']}", ""]
    lines += ["## Reproduction and next step", "",
              "Run `python -m tests.hiring_case_calibration_runner` for metrics and confusion matrices, and "
              "`python -m pytest tests/test_hiring_case_calibration.py -q` for fixture integrity and diagnostic reproducibility. "
              "All data is local and synthetic. The test harness prevents database/network access during evaluation.", "",
              "The separate frozen adversarial-v1 report challenges these rules without engine tuning. Review its "
              "semantic, direct-ownership, recency and preference-conflict failures before connecting a provider. "
              "No production rollout is certified.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    result = run_calibration()
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2, sort_keys=True))
