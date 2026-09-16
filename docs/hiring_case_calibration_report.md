# Hiring Case calibration report

Reference: hiring-case-calibration-v1. Production baseline: shadow adapter a736bed.

## Review status and method

These are 40 fictional, agent-authored cases awaiting human review, NOT a completed human-reviewed gold set. The expectations below are explicit proposed judgments under the product philosophy. No reviewer approval is claimed. 38 cases are normative proposals; 2 are exploratory because commute cost is unknown. All review statuses are pending.

Expected classifications, strength, value and requirement states were authored separately from execution. They are not produced by the engine. Facts alone are projected through versioned Candidate/Job Profile contracts and a deterministic fake interpreter; expected labels never enter that projection. Each of 20 pairs changes one declared fact field/subtree. Related serialized fields follow from that same fact.

Legacy comparison uses independently assigned synthetic fixture recommendations through the existing compatibility map, NOT fresh historical predictions or live AI. The two reject labels are unmapped by that map. These agreement figures measure reproducibility of this reference set, not population accuracy or improvement over production.

No production classification or UI behavior changed. The versioned profile contracts, server-only snapshot schema and profile-based shadow path are exercised offline. No network, AI, Gmail or production database was used.

## Composition

| Scenario family | Cases |
| --- | ---: |
| business_analysis | 4 |
| customer_operations | 4 |
| customer_success | 4 |
| financial_crime_aml_kyc | 6 |
| fraud_risk | 8 |
| operations_management | 4 |
| technical_operations | 4 |
| technical_support | 6 |

Expected distribution (not balanced to a quota): best_match=22, ineligible=2, skip_for_now=2, worth_a_try=7, youre_strong_but=7.

## Agreement

- Shadow/reference: 34/40 (85.0%); 6 label mismatches.
- Normative only: 33/38 (86.8%); exploratory: 1/2.
- Legacy/reference: 27/38 mapped (71.1%); 2 unmapped. Across all 40: 27/40; unmapped rows are not counted as correct.
- Strength disagreements: 3; opportunity value disagreements: 5.
- Requirement evidence disagreements: 1 across 46 requirements; importance disagreements: 2.
- 9 cases have at least one disagreement, including cases with the same final category.

## Confusion matrices

Rows are proposed reference labels. Columns are observed labels. Abstention remains explicit.

### Shadow

| Expected | best_match | worth_a_try | youre_strong_but | skip_for_now | ineligible | not_evaluated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best_match | 19 | 1 | 2 | 0 | 0 | 0 |
| worth_a_try | 1 | 6 | 0 | 0 | 0 | 0 |
| youre_strong_but | 2 | 0 | 5 | 0 | 0 | 0 |
| skip_for_now | 0 | 0 | 0 | 2 | 0 | 0 |
| ineligible | 0 | 0 | 0 | 0 | 2 | 0 |

### Legacy equivalent

| Expected | best_match | worth_a_try | youre_strong_but | skip_for_now | ineligible | unmapped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best_match | 17 | 3 | 2 | 0 | 0 | 0 |
| worth_a_try | 2 | 5 | 0 | 0 | 0 | 0 |
| youre_strong_but | 2 | 0 | 5 | 0 | 0 | 0 |
| skip_for_now | 0 | 2 | 0 | 0 | 0 | 0 |
| ineligible | 0 | 0 | 0 | 0 | 0 | 2 |

## Error taxonomy

Each discrepant case has one authored primary diagnostic attribution, pending reviewer confirmation. It is a hypothesis supported by the controlled pair, not an automatic semantic root-cause detector. Counts below distinguish final-label failures from any-dimension failures.

| Primary cause | Label mismatches | Any-dimension cases |
| --- | ---: | ---: |
| A_REQUIREMENT_EXTRACTION | 0 | 2 |
| B_EVIDENCE_LINKING | 0 | 0 |
| C_CAPABILITY_INTERPRETATION | 0 | 0 |
| D_OPPORTUNITY_VALUE | 3 | 4 |
| E_CLASSIFICATION_LOGIC | 1 | 1 |
| F_INSUFFICIENT_DATA | 1 | 1 |
| G_EXPECTED_CASE_NEEDS_REVIEW | 1 | 1 |

## Main findings

The most common attributed category remains OPPORTUNITY VALUE. The new path now consumes a known unacceptable salary reduction, work-content conflicts and severe seniority mismatch, but urgency, nuanced down-leveling and the strategic meaning of a strong offer remain incomplete (HC06, HC18b and HC19b). Unknown salary remains UNKNOWN, not negative.

The explicit evidence-authority boundary fixes the prior HC07b failure: a vague capability label attached to an experience ID remains EVIDENCE_MISSING. An ID establishes provenance, not evidence quality. PROVEN and TRANSFERABLE now require a valid source ref plus a structured semantic link.

The profile-based fake interpreter resolves the HC03b paraphrase without exact text matching. HC12b correctly remains EVIDENCE_MISSING because the source ID is absent; whether the reference should expect PROVEN requires an import-repair policy, not weaker authority. HC11b and HC16b expose hard-extraction importance loss.

Structured seniority context now weakens HC10b and HC17b as intended. HC18b still demonstrates a value-model gap: capability remains strong, but substantial down-leveling is not yet represented precisely enough.

The quadrant function agrees with all 40 authored reference strength/value pairs. This does not validate the entire classification pipeline: HC15b has correct evidence states but the engine treats an IMPORTANT transferable delivery requirement as strong overall; the proposed judgment is only viable. Human review must confirm this semantic strength policy before changing it. No numeric thresholds or category quotas were tuned.

HC06b and HC11b demonstrate why final-label agreement is insufficient: value or strength is wrong even though the resulting label happens to agree. HC20b is exploratory: without commute cost the reference MEDIUM value is debatable, so it is not a definitive product defect.

## Controlled pairs

Every row represents two cases; all fact changes must stay within the declared path. Expected outputs may change as a consequence. Tests verify the fact diff independently of expected labels.

| Pair | Only changed variable | Expected a -> b | Shadow a -> b |
| --- | --- | --- | --- |
| P01 | candidate.capabilities.0.proof | best_match -> worth_a_try | best_match -> worth_a_try |
| P02 | candidate.capabilities.0.proof | best_match -> worth_a_try | best_match -> worth_a_try |
| P03 | candidate.capabilities.0.proof.wording | best_match -> best_match | best_match -> best_match |
| P04 | company.needs.1.importance | best_match -> worth_a_try | best_match -> worth_a_try |
| P05 | opportunity.compensation | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P06 | opportunity.timing | best_match -> youre_strong_but | youre_strong_but -> youre_strong_but |
| P07 | candidate.capabilities.0.proof | best_match -> worth_a_try | best_match -> worth_a_try |
| P08 | company.eligibility_blocker | best_match -> ineligible | best_match -> ineligible |
| P09 | opportunity.role_content | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P10 | candidate.context | best_match -> worth_a_try | best_match -> worth_a_try |
| P11 | company.needs.1.parsed_slot | skip_for_now -> skip_for_now | skip_for_now -> skip_for_now |
| P12 | candidate.capabilities.0.proof.source_available | best_match -> best_match | best_match -> worth_a_try |
| P13 | company.eligibility_blocker | best_match -> ineligible | best_match -> ineligible |
| P14 | opportunity.desired_family | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P15 | candidate.capabilities.1.proof | best_match -> worth_a_try | best_match -> best_match |
| P16 | company.needs.0.parsed_slot | best_match -> best_match | best_match -> best_match |
| P17 | candidate.context | best_match -> worth_a_try | best_match -> worth_a_try |
| P18 | candidate.context | best_match -> youre_strong_but | best_match -> best_match |
| P19 | opportunity.compensation | youre_strong_but -> best_match | youre_strong_but -> youre_strong_but |
| P20 | opportunity.work_mode | best_match -> youre_strong_but | best_match -> best_match |

## Case judgments

S/V = strength/value. Full company, candidate and opportunity facts are in tests/hiring_case_calibration_cases.py; they include specific work examples and trade-offs, not live user data.

| Case | Track | Expected label; S/V | Shadow label; S/V | Primary cause | Proposed rationale |
| --- | --- | --- | --- | --- | --- |
| HC01a | normative | best_match; strong/high | best_match; strong/high | none | Direct investigation evidence supports the target role. |
| HC01b | normative | worth_a_try; viable/high | worth_a_try; viable/high | none | Capability is stated, but no case can yet support the CV or interview. |
| HC02a | normative | best_match; strong/high | best_match; strong/high | none | The evidence directly matches investigator responsibilities. |
| HC02b | normative | worth_a_try; viable/high | worth_a_try; viable/high | none | Dispute investigation provides an adjacent bridge with domain limits. |
| HC03a | normative | best_match; strong/high | best_match; strong/high | none | Concrete investigation evidence supports the role. |
| HC03b | normative | best_match; strong/high | best_match; strong/high | none | Equivalent wording describes the same supported investigation, not less capability. |
| HC04a | normative | best_match; strong/high | best_match; strong/high | none | Investigation is proven and the SQL gap is peripheral. |
| HC04b | normative | worth_a_try; weak/high | worth_a_try; weak/high | none | The same SQL gap now prevents independent core delivery. |
| HC05a | normative | best_match; strong/high | best_match; strong/high | none | Direct AML proof, target work and a meaningful pay improvement align. |
| HC05b | normative | youre_strong_but; strong/low | youre_strong_but; strong/low | none | Ability is unchanged; the specified pay sacrifice defeats personal value. |
| HC06a | normative | best_match; strong/high | youre_strong_but; strong/medium | D_OPPORTUNITY_VALUE | Proven KYC ability plus urgent income continuity justifies this lateral bridge. |
| HC06b | normative | youre_strong_but; strong/low | youre_strong_but; strong/medium | D_OPPORTUNITY_VALUE | A stable candidate gains no progression from the identical lateral role. |
| HC07a | normative | best_match; strong/high | best_match; strong/high | none | A concrete defensible decision record supports a safe CV claim. |
| HC07b | normative | worth_a_try; viable/high | worth_a_try; viable/high | none | A matching skill label alone is not usable proof, even inside an experience record. |
| HC08a | normative | best_match; strong/high | best_match; strong/high | none | The target escalation role is feasible and supported. |
| HC08b | normative | ineligible; ineligible/high | ineligible; ineligible/high | none | Mandatory relocation is an upstream blocker regardless of fit or attractiveness. |
| HC09a | normative | best_match; strong/high | best_match; strong/high | none | Supported work also matches the candidate's content preference. |
| HC09b | normative | youre_strong_but; strong/low | youre_strong_but; strong/low | none | The candidate can do the work but explicitly wants to stop doing it. |
| HC10a | normative | best_match; strong/high | best_match; strong/high | none | Independent incident delivery matches company scope. |
| HC10b | normative | worth_a_try; weak/high | worth_a_try; weak/high | none | Real examples exist, but the independent seniority/context demand is not met. |
| HC11a | normative | skip_for_now; weak/low | skip_for_now; weak/low | none | Independent SQL investigation is a core gap and the candidate explicitly avoids this work. |
| HC11b | normative | skip_for_now; weak/low | skip_for_now; viable/low | A_REQUIREMENT_EXTRACTION | A parser storing an unwanted role's core tool in a generic tools list must not reduce its materiality. |
| HC12a | normative | best_match; strong/high | best_match; strong/high | none | The reproducible defect example supports the target role. |
| HC12b | normative | best_match; strong/high | worth_a_try; viable/high | F_INSUFFICIENT_DATA | The same documented example exists, but its database experience ID was lost during import. |
| HC13a | normative | best_match; strong/high | best_match; strong/high | none | Supported recovery work fits the candidate's direction. |
| HC13b | normative | ineligible; ineligible/high | ineligible; ineligible/high | none | The hard scheduling conflict overrides the otherwise strong case. |
| HC14a | normative | best_match; strong/high | best_match; strong/high | none | The role is in the candidate's current chosen family. |
| HC14b | normative | youre_strong_but; strong/medium | youre_strong_but; strong/medium | none | A capable lateral fallback has limited value relative to the new analysis target. |
| HC15a | normative | best_match; strong/high | best_match; strong/high | none | Requirements work and important delivery responsibilities are directly evidenced. |
| HC15b | normative | worth_a_try; viable/high | best_match; strong/high | E_CLASSIFICATION_LOGIC | Delivery ownership is important enough that an adjacent bridge leaves the overall case viable, not strong. |
| HC16a | normative | best_match; strong/high | best_match; strong/high | none | An explicit core need and direct proof make a strong case. |
| HC16b | normative | best_match; strong/high | best_match; strong/high | A_REQUIREMENT_EXTRACTION | The same core need remains real when the parsed profile puts it in unstructured important details. |
| HC17a | normative | best_match; strong/high | best_match; strong/high | none | Real leadership evidence and comparable scale support this management role. |
| HC17b | normative | worth_a_try; weak/high | worth_a_try; weak/high | none | A genuine team-leading example does not prove the required management scale. |
| HC18a | normative | best_match; strong/high | best_match; strong/high | none | Evidenced leadership and first formal progression make this valuable. |
| HC18b | normative | youre_strong_but; strong/low | best_match; strong/high | D_OPPORTUNITY_VALUE | Overqualification does not erase ability, but the role sacrifices the stated strategic scope. |
| HC19a | normative | youre_strong_but; strong/medium | youre_strong_but; strong/medium | none | Unknown salary is not a penalty; this otherwise lateral option has only uncertain upside. |
| HC19b | normative | best_match; strong/high | youre_strong_but; strong/medium | D_OPPORTUNITY_VALUE | The known and explicitly valued salary improvement makes the same supported role attractive. |
| HC20a | exploratory | best_match; strong/high | best_match; strong/high | none | Remote target work appears valuable; confirm remaining conditions before accepting. |
| HC20b | exploratory | youre_strong_but; strong/medium | best_match; strong/high | G_EXPECTED_CASE_NEEDS_REVIEW | Provisional value depends on the unmeasured commute; high value is also defensible if costs are small. |

## Proof and representation review

CV-safe means only the demonstrated scope. Transferable examples must stay framed as adjacent experience; no table entry licenses claims of greater ownership or seniority. Capability and evidence are separate facts.

| Case / requirement | Capability exists | Evidence exists / relationship | Interview defensible | CV safe | Ask for evidence | Expected state |
| --- | --- | --- | --- | --- | --- | --- |
| HC01a / Investigate fraud patterns | yes | True / direct | True | True | False | proven |
| HC01b / Investigate fraud patterns | yes | False / absent | False | False | True | evidence_missing |
| HC02a / Investigate fraud patterns | yes | True / direct | True | True | False | proven |
| HC02b / Investigate fraud patterns | yes | True / transferable | True | True | False | transferable |
| HC03a / Investigate fraud patterns | yes | True / direct | True | True | False | proven |
| HC03b / Investigate fraud patterns | yes | True / direct | True | True | False | proven |
| HC04a / Investigate fraud patterns | yes | True / direct | True | True | False | proven |
| HC04a / Write SQL investigation queries | no | False / confirmed_gap | False | False | False | gap |
| HC04b / Investigate fraud patterns | yes | True / direct | True | True | False | proven |
| HC04b / Write SQL investigation queries | no | False / confirmed_gap | False | False | False | gap |
| HC05a / Review AML transaction alerts | yes | True / direct | True | True | False | proven |
| HC05b / Review AML transaction alerts | yes | True / direct | True | True | False | proven |
| HC06a / Review corporate KYC files | yes | True / direct | True | True | False | proven |
| HC06b / Review corporate KYC files | yes | True / direct | True | True | False | proven |
| HC07a / Document suspicious activity decisions | yes | True / direct | True | True | False | proven |
| HC07b / Document suspicious activity decisions | yes | False / vague | False | False | True | evidence_missing |
| HC08a / Resolve complex escalations | yes | True / direct | True | True | False | proven |
| HC08b / Resolve complex escalations | yes | True / direct | True | True | False | proven |
| HC09a / Resolve complex escalations | yes | True / direct | True | True | False | proven |
| HC09b / Resolve complex escalations | yes | True / direct | True | True | False | proven |
| HC10a / Diagnose application incidents | yes | True / direct | True | True | False | proven |
| HC10b / Diagnose application incidents | yes | True / direct | True | True | False | proven |
| HC11a / Diagnose application incidents | yes | True / direct | True | True | False | proven |
| HC11a / Query production logs with SQL | no | False / confirmed_gap | False | False | False | gap |
| HC11b / Diagnose application incidents | yes | True / direct | True | True | False | proven |
| HC11b / Query production logs with SQL | no | False / confirmed_gap | False | False | False | gap |
| HC12a / Reproduce software defects | yes | True / direct | True | True | False | proven |
| HC12b / Reproduce software defects | yes | True / direct | True | True | False | proven |
| HC13a / Restore failed scheduled jobs | yes | True / direct | True | True | False | proven |
| HC13b / Restore failed scheduled jobs | yes | True / direct | True | True | False | proven |
| HC14a / Restore failed scheduled jobs | yes | True / direct | True | True | False | proven |
| HC14b / Restore failed scheduled jobs | yes | True / direct | True | True | False | proven |
| HC15a / Map operational requirements | yes | True / direct | True | True | False | proven |
| HC15a / Coordinate cross-functional delivery | yes | True / direct | True | True | False | proven |
| HC15b / Map operational requirements | yes | True / direct | True | True | False | proven |
| HC15b / Coordinate cross-functional delivery | yes | True / transferable | True | True | False | transferable |
| HC16a / Map operational requirements | yes | True / direct | True | True | False | proven |
| HC16b / Map operational requirements | yes | True / direct | True | True | False | proven |
| HC17a / Lead operational teams | yes | True / direct | True | True | False | proven |
| HC17b / Lead operational teams | yes | True / direct | True | True | False | proven |
| HC18a / Lead operational teams | yes | True / direct | True | True | False | proven |
| HC18b / Lead operational teams | yes | True / direct | True | True | False | proven |
| HC19a / Plan customer adoption | yes | True / direct | True | True | False | proven |
| HC19b / Plan customer adoption | yes | True / direct | True | True | False | proven |
| HC20a / Plan customer adoption | yes | True / direct | True | True | False | proven |
| HC20b / Plan customer adoption | yes | True / direct | True | True | False | proven |

## Evidence-missing review

Union of reference EVIDENCE_MISSING and shadow EVIDENCE_MISSING. This catches both missed valid proof and unsupported proof that the shadow incorrectly accepts. Real GAP confirmations remain separate.

### HC01b: Investigate fraud patterns

- Plausibly present: True; reference missing: True; shadow missing: True.
- Existing record: No investigation example is stored.
- Resolving evidence: A concrete case describing personal actions, methods, decisions and outcome.
- First action: Ask for a real example; do not assume it exists.
- Future Add Evidence question: Have you personally performed this work: investigate fraud patterns?

### HC07b: Document suspicious activity decisions

- Plausibly present: True; reference missing: True; shadow missing: True.
- Existing record: Claims familiarity but cannot provide any personal decision, action or outcome.
- Resolving evidence: A concrete case describing personal actions, methods, decisions and outcome.
- First action: Ask for a real example; do not assume it exists.
- Future Add Evidence question: Have you personally performed this work: document suspicious activity decisions?

### HC12b: Reproduce software defects

- Plausibly present: True; reference missing: False; shadow missing: True.
- Existing record: Produced a minimal reproduction, captured logs and validated the release containing the fix.
- Resolving evidence: A concrete case describing personal actions, methods, decisions and outcome.
- First action: Review and link the already supplied evidence before asking the candidate again.
- Future Add Evidence question: Have you personally performed this work: reproduce software defects?

## Reproduction and next step

Run `python -m tests.hiring_case_calibration_runner` for metrics and confusion matrices, and `python -m pytest tests/test_hiring_case_calibration.py -q` for fixture integrity and diagnostic reproducibility. All data is local and synthetic. The test harness prevents database/network access during evaluation.

The usable-proof boundary is now explicit in the profile path: valid source refs and structured semantic links are required; checkpoint prose and vague attributed labels cannot self-confirm. The smallest next implementation is a reviewed, offline provider adapter that produces these contracts from hard facts.

Salary units, timing and seniority/value trade-offs still need richer explicit fact contracts. This pass does not switch production classification or certify a rollout.
