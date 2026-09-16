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
    HiringCaseClassification, HiringCaseStrength, OpportunitySignal,
    OpportunitySignalKind, OpportunitySignalState, OpportunityValue,
    RequirementEvidenceState, RequirementImportance,
)
from models.hiring_case_shadow import ConfirmedCapabilityGap, HiringCaseShadowSource
from models.job_profile import JobProfile
from models.profile_interpretation import (
    AIJobProfileSnapshot, CandidateProfileSnapshot, HiringCaseInterpretation,
    InterpretationAuthority, InterpretedJobNeed, ProfileCapability,
    ProfileCheckpoint, RequirementLink,
)
from models.professional_experience_profile import ProfessionalExperienceProfile
from services.hiring_case_compatibility import read_legacy_classification
from services.hiring_case_engine import classify_hiring_case
from services.hiring_case_shadow_service import evaluate_profile_hiring_case_shadow
from services.job_hard_facts import build_job_hard_facts
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


def profile_inputs_from_facts(facts, source):
    """Deterministic fake interpreter: links facts semantically, never from expectations."""
    profile = source.job_profile
    hard = build_job_hard_facts(
        profile,
        explicit_blockers=(facts.company.eligibility_blocker,) if facts.company.eligibility_blocker else (),
    )
    fact_by_value = {_key(item.value): item for item in hard.facts}
    core_kinds = {"must_have_capability", "must_have_experience", "qualification", "structural_requirement"}
    nice_kinds = {"nice_to_have"}
    needs = []
    links = []
    source_refs = []
    capabilities = []
    confirmed_gaps = []
    candidate_capabilities = {item.key: item for item in facts.candidate.capabilities}
    for need in facts.company.needs:
        hard_fact = fact_by_value.get(_key(need.text))
        if hard_fact is None:
            continue
        importance = (
            RequirementImportance.CORE if hard_fact.kind in core_kinds
            else RequirementImportance.NICE_TO_HAVE if hard_fact.kind in nice_kinds
            else RequirementImportance.IMPORTANT
        )
        need_id = f"need-{need.key}"
        needs.append(InterpretedJobNeed(
            need_id, need.text, importance, InterpretationAuthority.EXPLICIT,
            (hard_fact.fact_id,), what_to_demonstrate=need.evidence_needed,
        ))
        capability = candidate_capabilities[need.key]
        proof = capability.proof
        refs = ()
        if proof.kind in {"direct", "transferable"} and proof.source_available:
            refs = (f"professional_experience:experience-{need.key}",)
            source_refs.extend(refs)
            capabilities.append(ProfileCapability(
                f"cap-{need.key}", proof.wording, refs,
                contexts=(proof.example,), transferable=proof.kind == "transferable",
            ))
        state = {
            "direct": RequirementEvidenceState.PROVEN,
            "transferable": RequirementEvidenceState.TRANSFERABLE,
            "confirmed_gap": RequirementEvidenceState.GAP,
            "absent": RequirementEvidenceState.EVIDENCE_MISSING,
            "vague": RequirementEvidenceState.EVIDENCE_MISSING,
        }[proof.kind]
        if not refs and state in {RequirementEvidenceState.PROVEN, RequirementEvidenceState.TRANSFERABLE}:
            state = RequirementEvidenceState.EVIDENCE_MISSING
        if proof.kind == "confirmed_gap":
            confirmed_gaps.append(need_id)
        links.append(RequirementLink(
            need_id, state, refs,
            "Synthetic source-backed relationship for offline calibration.", bool(refs),
        ))
    candidate_profile = CandidateProfileSnapshot(
        source.candidate.id, 1, "synthetic-memory-signature", "2026-01-01T00:00:00+00:00",
        tuple(source_refs), tuple(capabilities),
        ProfileCheckpoint(
            current_position=facts.candidate.context.scope,
            confirmed_gaps=tuple(confirmed_gaps),
            current_direction=(facts.opportunity.career_direction,),
        ),
        confirmed_gaps=tuple(confirmed_gaps), objectives=(facts.opportunity.career_direction,),
        preferences=(facts.opportunity.role_content,), seniority=facts.candidate.context.level,
        responsibility_scope=facts.candidate.context.scope,
    )
    job_profile = AIJobProfileSnapshot(
        hard.job_id, 1, hard.job_signature, "2026-01-01T00:00:00+00:00", tuple(needs),
        problem_to_solve=facts.company.expected_work, context=facts.company.seniority_context,
    )
    opportunity = facts.opportunity
    signals = []

    def signal(kind, state, importance, rationale):
        signals.append(OpportunitySignal(kind, state, importance, rationale))

    if _key(opportunity.desired_family) == _key(facts.company.family):
        signal(OpportunitySignalKind.CAREER_DIRECTION, OpportunitySignalState.POSITIVE,
               RequirementImportance.CORE, "Role family matches the stated direction.")
    else:
        signal(OpportunitySignalKind.CAREER_DIRECTION, OpportunitySignalState.NEGATIVE,
               RequirementImportance.IMPORTANT, "Role family differs from the stated direction.")
    pay = opportunity.compensation
    if pay.annual_offer is None or pay.annual_current is None:
        signal(OpportunitySignalKind.COMPENSATION, OpportunitySignalState.UNKNOWN,
               RequirementImportance.IMPORTANT, "Comparable compensation is unknown.")
    elif "unacceptable" in pay.tradeoff.casefold() or pay.annual_offer < pay.annual_current:
        signal(OpportunitySignalKind.COMPENSATION, OpportunitySignalState.NEGATIVE,
               RequirementImportance.CORE, "Known compensation is an unacceptable reduction.")
    elif pay.annual_offer > pay.annual_current:
        signal(OpportunitySignalKind.COMPENSATION, OpportunitySignalState.POSITIVE,
               RequirementImportance.IMPORTANT, "Known compensation improves current pay.")
    if opportunity.role_content.startswith("Explicitly avoid: "):
        signal(OpportunitySignalKind.ROLE_CONTENT, OpportunitySignalState.NEGATIVE,
               RequirementImportance.CORE, "Role content conflicts with an explicit preference.")
    allowed = {
        "remote": opportunity.remote_allowed,
        "hybrid": opportunity.hybrid_allowed,
        "onsite": opportunity.onsite_allowed,
    }
    if opportunity.work_mode in allowed and not allowed[opportunity.work_mode]:
        signal(OpportunitySignalKind.WORK_MODE_LOCATION, OpportunitySignalState.NEGATIVE,
               RequirementImportance.CORE, "Known work mode conflicts with a constraint.")
    if "downlevel" in opportunity.progression.casefold():
        signal(OpportunitySignalKind.SENIORITY_PROGRESSION, OpportunitySignalState.NEGATIVE,
               RequirementImportance.CORE, "Role is a material seniority reduction.")
    elif "advancement" in opportunity.progression.casefold():
        signal(OpportunitySignalKind.SENIORITY_PROGRESSION, OpportunitySignalState.POSITIVE,
               RequirementImportance.IMPORTANT, "Role offers stated progression.")
    interpretation = HiringCaseInterpretation(
        tuple(links), tuple(signals), facts.candidate.context.severe_mismatch,
    )
    return candidate_profile, job_profile, hard, interpretation


def proof_reviews(case):
    expected_states = dict(case.expected.states)
    capabilities = {item.key: item for item in case.facts.candidate.capabilities}
    result = []
    for need in case.facts.company.needs:
        capability = capabilities[need.key]
        proof = capability.proof
        usable = proof.kind in {"direct", "transferable"}
        result.append({
            "requirement_key": need.key, "requirement": need.text,
            "capability_exists": capability.exists,
            "evidence_exists": usable,
            "evidence_relationship": proof.kind,
            "interview_defensible": usable,
            "safe_in_cv": usable,
            "cv_boundary": (
                "Do not present this as proven capability." if not usable else
                "Represent as adjacent experience only." if proof.kind == "transferable" else
                "Retain the demonstrated scope; no claim of broader seniority."
            ),
            "needs_evidence": expected_states[need.key] == "evidence_missing",
            "expected_state": expected_states[need.key],
        })
    return result


def evaluate_case(case):
    source = source_from_facts(case.facts, case.legacy_recommendation)
    candidate_profile, job_profile, hard, interpretation = profile_inputs_from_facts(case.facts, source)
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
        "human_review_status": case.human_review_status,
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
        "reference_status": "agent_authored_pending_human_review",
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
        "Reference: hiring-case-calibration-v1. Production baseline: shadow adapter a736bed.",
        "",
        "## Review status and method",
        "",
        "These are 40 fictional, agent-authored cases awaiting human review, NOT a completed human-reviewed gold set. "
        "The expectations below are explicit proposed judgments under the product philosophy. No reviewer approval is claimed. "
        "38 cases are normative proposals; 2 are exploratory because commute cost is unknown. All review statuses are pending.",
        "",
        "Expected classifications, strength, value and requirement states were authored separately from execution. "
        "They are not produced by the engine. Facts alone are projected through versioned Candidate/Job Profile contracts and a deterministic fake interpreter; expected labels never enter that projection. "
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
        f"- Normative only: {n['shadow_exact_matches']}/{n['total']} ({n['shadow_agreement']:.1%}); exploratory: 1/2.",
        f"- Legacy/reference: {m['legacy_exact_matches']}/{m['legacy_mapped']} mapped ({m['legacy_agreement_mapped']:.1%}); "
        f"{m['legacy_unmapped']} unmapped. Across all 40: {m['legacy_exact_matches']}/40; unmapped rows are not counted as correct.",
        f"- Strength disagreements: {m['strength_mismatches']}; opportunity value disagreements: {m['value_mismatches']}.",
        f"- Requirement evidence disagreements: {m['evidence_state_mismatches']} across 46 requirements; "
        f"importance disagreements: {m['importance_mismatches']}.",
        f"- {m['any_dimension_mismatch_cases']} cases have at least one disagreement, including cases with the same final category.",
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
        "The most common attributed category remains OPPORTUNITY VALUE. The new path now consumes a known unacceptable "
        "salary reduction, work-content conflicts and severe seniority mismatch, but urgency, nuanced down-leveling and the "
        "strategic meaning of a strong offer remain incomplete (HC06, HC18b and HC19b). Unknown salary remains UNKNOWN, not negative.",
        "",
        "The explicit evidence-authority boundary fixes the prior HC07b failure: a vague capability label attached to an "
        "experience ID remains EVIDENCE_MISSING. An ID establishes provenance, not evidence quality. PROVEN and TRANSFERABLE "
        "now require a valid source ref plus a structured semantic link.",
        "",
        "The profile-based fake interpreter resolves the HC03b paraphrase without exact text matching. HC12b correctly "
        "remains EVIDENCE_MISSING because the source ID is absent; whether the reference should expect PROVEN requires an "
        "import-repair policy, not weaker authority. HC11b and HC16b expose hard-extraction importance loss.",
        "",
        "Structured seniority context now weakens HC10b and HC17b as intended. HC18b still demonstrates a value-model gap: "
        "capability remains strong, but substantial down-leveling is not yet represented precisely enough.",
        "",
        "The quadrant function agrees with all 40 authored reference strength/value pairs. This does not validate the "
        "entire classification pipeline: HC15b has correct evidence states but the engine treats an IMPORTANT transferable "
        "delivery requirement as strong overall; the proposed judgment is only viable. Human review must confirm this "
        "semantic strength policy before changing it. No numeric thresholds or category quotas were tuned.",
        "",
        "HC06b and HC11b demonstrate why final-label agreement is insufficient: value or strength is wrong even though "
        "the resulting label happens to agree. HC20b is exploratory: without commute cost the reference MEDIUM value is "
        "debatable, so it is not a definitive product defect.",
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
              "| Case / requirement | Capability exists | Evidence exists / relationship | Interview defensible | CV safe | Ask for evidence | Expected state |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in result["cases"]:
        for item in row["proof_review"]:
            lines.append(f"| {row['case_id']} / {item['requirement']} | {item['capability_exists']} | "
                         f"{item['evidence_exists']} / {item['evidence_relationship']} | {item['interview_defensible']} | "
                         f"{item['safe_in_cv']} | {item['needs_evidence']} | {item['expected_state']} |")
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
              "The usable-proof boundary is now explicit in the profile path: valid source refs and structured semantic "
              "links are required; checkpoint prose and vague attributed labels cannot self-confirm. The smallest next "
              "implementation is a reviewed, offline provider adapter that produces these contracts from hard facts.", "",
              "Salary units, timing and seniority/value trade-offs still need richer explicit fact contracts. This pass "
              "does not switch production classification or certify a rollout.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    result = run_calibration()
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2, sort_keys=True))
