# Hiring Case calibration report

Reference: hiring-case-calibration-v1. Offline structured interpreter v1; baseline b5d019e.

## Review status and method

These are 40 fictional, agent-authored cases awaiting human review, NOT a completed human-reviewed gold set. The expectations below are explicit proposed judgments under the product philosophy. No reviewer approval is claimed. HC12b, HC15b and HC20b were reviewed by the user. The other 37 judgments remain pending. Original track membership is preserved.

Expected classifications, strength, value and requirement states were authored separately from execution. They are not produced by the engine. Facts alone are projected through versioned Candidate/Job Profile contracts and four signature-keyed fixture operations with strict validation; expected labels never enter that projection. Each of 20 pairs changes one declared fact field/subtree. Related serialized fields follow from that same fact.

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

Expected distribution (not balanced to a quota): best_match=23, ineligible=2, skip_for_now=2, worth_a_try=7, youre_strong_but=6.

## Agreement

- Shadow/reference: 40/40 (100.0%); 0 label mismatches.
- Normative only: 38/38 (100.0%); exploratory: 2/2.
- Legacy/reference: 28/38 mapped (73.7%); 2 unmapped. Across all 40: 28/40; unmapped rows are not counted as correct.
- Strength disagreements: 0; opportunity value disagreements: 0.
- Requirement evidence disagreements: 0 across 46 requirements; importance disagreements: 0.
- 0 cases have at least one disagreement, including cases with the same final category.
- Authority violations: 0; unavailable operations: 0.
- Reviewed confidence: 1/1 (HC20b: MEDIUM).

## Confusion matrices

Rows are proposed reference labels. Columns are observed labels. Abstention remains explicit.

### Shadow

| Expected | best_match | worth_a_try | youre_strong_but | skip_for_now | ineligible | not_evaluated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best_match | 23 | 0 | 0 | 0 | 0 | 0 |
| worth_a_try | 0 | 7 | 0 | 0 | 0 | 0 |
| youre_strong_but | 0 | 0 | 6 | 0 | 0 | 0 |
| skip_for_now | 0 | 0 | 0 | 2 | 0 | 0 |
| ineligible | 0 | 0 | 0 | 0 | 2 | 0 |

### Legacy equivalent

| Expected | best_match | worth_a_try | youre_strong_but | skip_for_now | ineligible | unmapped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best_match | 18 | 3 | 2 | 0 | 0 | 0 |
| worth_a_try | 2 | 5 | 0 | 0 | 0 | 0 |
| youre_strong_but | 1 | 0 | 5 | 0 | 0 | 0 |
| skip_for_now | 0 | 2 | 0 | 0 | 0 | 0 |
| ineligible | 0 | 0 | 0 | 0 | 0 | 2 |

## Error taxonomy

Each discrepant case has one authored primary diagnostic attribution, pending reviewer confirmation. It is a hypothesis supported by the controlled pair, not an automatic semantic root-cause detector. Counts below distinguish final-label failures from any-dimension failures.

| Primary cause | Label mismatches | Any-dimension cases |
| --- | ---: | ---: |
| A_REQUIREMENT_EXTRACTION | 0 | 0 |
| B_EVIDENCE_LINKING | 0 | 0 |
| C_CAPABILITY_INTERPRETATION | 0 | 0 |
| D_OPPORTUNITY_VALUE | 0 | 0 |
| E_CLASSIFICATION_LOGIC | 0 | 0 |
| F_INSUFFICIENT_DATA | 0 | 0 |
| G_EXPECTED_CASE_NEEDS_REVIEW | 0 | 0 |

## Main findings

The fixture interpreter supplies authored semantic links and value interpretations, not keyword matching. Known salary trade-offs, timing and down-leveling are represented explicitly. Unknown salary remains UNKNOWN. These hypothetical responses test contracts; they do not demonstrate that a real provider can interpret these cases correctly.

HC12b: EVIDENCE_MISSING / VIABLE / HIGH / WORTH_A_TRY. Existing evidence has broken provenance, not a capability gap. SOURCE_REFERENCE_UNAVAILABLE, needs_evidence=false, needs_source_repair=true.

HC15b: STRONG / HIGH / BEST_MATCH. Defensible IMPORTANT transferable support does not automatically downgrade proven CORE needs. Direct ownership must be explicitly required; adjacent scope is preserved.

HC20b: STRONG / HIGH / BEST_MATCH with MEDIUM confidence. Unknown commute cost is not a known negative. UNCERTAINTY CHANGES CONFIDENCE BEFORE IT CHANGES VALENCE. Confidence remains coarse: another unknown fact need not lower an already MEDIUM bucket.

This means the reviewed reference set and implementation agree. It does NOT establish real-world AI accuracy. Only the three specified judgments changed; the other 37 expectations and all original facts are frozen.

All 40 fixture pipelines passed structural/source authority validation without abstention. Adversarial tests separately exercise rejected and normalized outputs. Existing references cannot prove semantic entailment: a false assertion citing a real source still requires semantic evaluation by humans or a future provider.

## Controlled pairs

Every row represents two cases; all fact changes must stay within the declared path. Expected outputs may change as a consequence. Tests verify the fact diff independently of expected labels.

| Pair | Only changed variable | Expected a -> b | Shadow a -> b |
| --- | --- | --- | --- |
| P01 | candidate.capabilities.0.proof | best_match -> worth_a_try | best_match -> worth_a_try |
| P02 | candidate.capabilities.0.proof | best_match -> worth_a_try | best_match -> worth_a_try |
| P03 | candidate.capabilities.0.proof.wording | best_match -> best_match | best_match -> best_match |
| P04 | company.needs.1.importance | best_match -> worth_a_try | best_match -> worth_a_try |
| P05 | opportunity.compensation | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P06 | opportunity.timing | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P07 | candidate.capabilities.0.proof | best_match -> worth_a_try | best_match -> worth_a_try |
| P08 | company.eligibility_blocker | best_match -> ineligible | best_match -> ineligible |
| P09 | opportunity.role_content | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P10 | candidate.context | best_match -> worth_a_try | best_match -> worth_a_try |
| P11 | company.needs.1.parsed_slot | skip_for_now -> skip_for_now | skip_for_now -> skip_for_now |
| P12 | candidate.capabilities.0.proof.source_available | best_match -> worth_a_try | best_match -> worth_a_try |
| P13 | company.eligibility_blocker | best_match -> ineligible | best_match -> ineligible |
| P14 | opportunity.desired_family | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P15 | candidate.capabilities.1.proof | best_match -> best_match | best_match -> best_match |
| P16 | company.needs.0.parsed_slot | best_match -> best_match | best_match -> best_match |
| P17 | candidate.context | best_match -> worth_a_try | best_match -> worth_a_try |
| P18 | candidate.context | best_match -> youre_strong_but | best_match -> youre_strong_but |
| P19 | opportunity.compensation | youre_strong_but -> best_match | youre_strong_but -> best_match |
| P20 | opportunity.work_mode | best_match -> best_match | best_match -> best_match |

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
| HC06a | normative | best_match; strong/high | best_match; strong/high | none | Proven KYC ability plus urgent income continuity justifies this lateral bridge. |
| HC06b | normative | youre_strong_but; strong/low | youre_strong_but; strong/low | none | A stable candidate gains no progression from the identical lateral role. |
| HC07a | normative | best_match; strong/high | best_match; strong/high | none | A concrete defensible decision record supports a safe CV claim. |
| HC07b | normative | worth_a_try; viable/high | worth_a_try; viable/high | none | A matching skill label alone is not usable proof, even inside an experience record. |
| HC08a | normative | best_match; strong/high | best_match; strong/high | none | The target escalation role is feasible and supported. |
| HC08b | normative | ineligible; ineligible/high | ineligible; ineligible/high | none | Mandatory relocation is an upstream blocker regardless of fit or attractiveness. |
| HC09a | normative | best_match; strong/high | best_match; strong/high | none | Supported work also matches the candidate's content preference. |
| HC09b | normative | youre_strong_but; strong/low | youre_strong_but; strong/low | none | The candidate can do the work but explicitly wants to stop doing it. |
| HC10a | normative | best_match; strong/high | best_match; strong/high | none | Independent incident delivery matches company scope. |
| HC10b | normative | worth_a_try; weak/high | worth_a_try; weak/high | none | Real examples exist, but the independent seniority/context demand is not met. |
| HC11a | normative | skip_for_now; weak/low | skip_for_now; weak/low | none | Independent SQL investigation is a core gap and the candidate explicitly avoids this work. |
| HC11b | normative | skip_for_now; weak/low | skip_for_now; weak/low | none | A parser storing an unwanted role's core tool in a generic tools list must not reduce its materiality. |
| HC12a | normative | best_match; strong/high | best_match; strong/high | none | The reproducible defect example supports the target role. |
| HC12b | normative | worth_a_try; viable/high | worth_a_try; viable/high | none | Reviewed: the example exists but its source ID was lost. Repair provenance; this is not a capability gap or a request for new evidence. |
| HC13a | normative | best_match; strong/high | best_match; strong/high | none | Supported recovery work fits the candidate's direction. |
| HC13b | normative | ineligible; ineligible/high | ineligible; ineligible/high | none | The hard scheduling conflict overrides the otherwise strong case. |
| HC14a | normative | best_match; strong/high | best_match; strong/high | none | The role is in the candidate's current chosen family. |
| HC14b | normative | youre_strong_but; strong/medium | youre_strong_but; strong/medium | none | A capable lateral fallback has limited value relative to the new analysis target. |
| HC15a | normative | best_match; strong/high | best_match; strong/high | none | Requirements work and important delivery responsibilities are directly evidenced. |
| HC15b | normative | best_match; strong/high | best_match; strong/high | none | Reviewed: defensible transferable IMPORTANT evidence does not downgrade proven CORE delivery; direct ownership was not mandatory. Preserve adjacent scope in representation. |
| HC16a | normative | best_match; strong/high | best_match; strong/high | none | An explicit core need and direct proof make a strong case. |
| HC16b | normative | best_match; strong/high | best_match; strong/high | none | The same core need remains real when the parsed profile puts it in unstructured important details. |
| HC17a | normative | best_match; strong/high | best_match; strong/high | none | Real leadership evidence and comparable scale support this management role. |
| HC17b | normative | worth_a_try; weak/high | worth_a_try; weak/high | none | A genuine team-leading example does not prove the required management scale. |
| HC18a | normative | best_match; strong/high | best_match; strong/high | none | Evidenced leadership and first formal progression make this valuable. |
| HC18b | normative | youre_strong_but; strong/low | youre_strong_but; strong/low | none | Overqualification does not erase ability, but the role sacrifices the stated strategic scope. |
| HC19a | normative | youre_strong_but; strong/medium | youre_strong_but; strong/medium | none | Unknown salary is not a penalty; this otherwise lateral option has only uncertain upside. |
| HC19b | normative | best_match; strong/high | best_match; strong/high | none | The known and explicitly valued salary improvement makes the same supported role attractive. |
| HC20a | exploratory | best_match; strong/high | best_match; strong/high | none | Remote target work appears valuable; confirm remaining conditions before accepting. |
| HC20b | exploratory | best_match; strong/high | best_match; strong/high | none | Reviewed: acceptable hybrid with unknown commute cost retains HIGH value, with reduced confidence. Uncertainty changes confidence before valence. |

## Proof and representation review

CV-safe means only the demonstrated scope. Transferable examples must stay framed as adjacent experience; no table entry licenses claims of greater ownership or seniority. Capability and evidence are separate facts.

| Case / requirement | Capability exists | Evidence exists / relationship | Interview defensible | CV safe | Ask for evidence | Repair source | Expected state |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HC01a / Investigate fraud patterns | yes | True / direct | True | True | False | False | proven |
| HC01b / Investigate fraud patterns | yes | False / absent | False | False | True | False | evidence_missing |
| HC02a / Investigate fraud patterns | yes | True / direct | True | True | False | False | proven |
| HC02b / Investigate fraud patterns | yes | True / transferable | True | True | False | False | transferable |
| HC03a / Investigate fraud patterns | yes | True / direct | True | True | False | False | proven |
| HC03b / Investigate fraud patterns | yes | True / direct | True | True | False | False | proven |
| HC04a / Investigate fraud patterns | yes | True / direct | True | True | False | False | proven |
| HC04a / Write SQL investigation queries | no | False / confirmed_gap | False | False | False | False | gap |
| HC04b / Investigate fraud patterns | yes | True / direct | True | True | False | False | proven |
| HC04b / Write SQL investigation queries | no | False / confirmed_gap | False | False | False | False | gap |
| HC05a / Review AML transaction alerts | yes | True / direct | True | True | False | False | proven |
| HC05b / Review AML transaction alerts | yes | True / direct | True | True | False | False | proven |
| HC06a / Review corporate KYC files | yes | True / direct | True | True | False | False | proven |
| HC06b / Review corporate KYC files | yes | True / direct | True | True | False | False | proven |
| HC07a / Document suspicious activity decisions | yes | True / direct | True | True | False | False | proven |
| HC07b / Document suspicious activity decisions | yes | False / vague | False | False | True | False | evidence_missing |
| HC08a / Resolve complex escalations | yes | True / direct | True | True | False | False | proven |
| HC08b / Resolve complex escalations | yes | True / direct | True | True | False | False | proven |
| HC09a / Resolve complex escalations | yes | True / direct | True | True | False | False | proven |
| HC09b / Resolve complex escalations | yes | True / direct | True | True | False | False | proven |
| HC10a / Diagnose application incidents | yes | True / direct | True | True | False | False | proven |
| HC10b / Diagnose application incidents | yes | True / direct | True | True | False | False | proven |
| HC11a / Diagnose application incidents | yes | True / direct | True | True | False | False | proven |
| HC11a / Query production logs with SQL | no | False / confirmed_gap | False | False | False | False | gap |
| HC11b / Diagnose application incidents | yes | True / direct | True | True | False | False | proven |
| HC11b / Query production logs with SQL | no | False / confirmed_gap | False | False | False | False | gap |
| HC12a / Reproduce software defects | yes | True / direct | True | True | False | False | proven |
| HC12b / Reproduce software defects | yes | True / direct | False | False | False | True | evidence_missing |
| HC13a / Restore failed scheduled jobs | yes | True / direct | True | True | False | False | proven |
| HC13b / Restore failed scheduled jobs | yes | True / direct | True | True | False | False | proven |
| HC14a / Restore failed scheduled jobs | yes | True / direct | True | True | False | False | proven |
| HC14b / Restore failed scheduled jobs | yes | True / direct | True | True | False | False | proven |
| HC15a / Map operational requirements | yes | True / direct | True | True | False | False | proven |
| HC15a / Coordinate cross-functional delivery | yes | True / direct | True | True | False | False | proven |
| HC15b / Map operational requirements | yes | True / direct | True | True | False | False | proven |
| HC15b / Coordinate cross-functional delivery | yes | True / transferable | True | True | False | False | transferable |
| HC16a / Map operational requirements | yes | True / direct | True | True | False | False | proven |
| HC16b / Map operational requirements | yes | True / direct | True | True | False | False | proven |
| HC17a / Lead operational teams | yes | True / direct | True | True | False | False | proven |
| HC17b / Lead operational teams | yes | True / direct | True | True | False | False | proven |
| HC18a / Lead operational teams | yes | True / direct | True | True | False | False | proven |
| HC18b / Lead operational teams | yes | True / direct | True | True | False | False | proven |
| HC19a / Plan customer adoption | yes | True / direct | True | True | False | False | proven |
| HC19b / Plan customer adoption | yes | True / direct | True | True | False | False | proven |
| HC20a / Plan customer adoption | yes | True / direct | True | True | False | False | proven |
| HC20b / Plan customer adoption | yes | True / direct | True | True | False | False | proven |

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

- Plausibly present: True; reference missing: True; shadow missing: True.
- Existing record: Produced a minimal reproduction, captured logs and validated the release containing the fix.
- Resolving evidence: A concrete case describing personal actions, methods, decisions and outcome.
- First action: Review and link the already supplied evidence before asking the candidate again.
- Future Add Evidence question: Have you personally performed this work: reproduce software defects?

## Reproduction and next step

Run `python -m tests.hiring_case_calibration_runner` for metrics and confusion matrices, and `python -m pytest tests/test_hiring_case_calibration.py -q` for fixture integrity and diagnostic reproducibility. All data is local and synthetic. The test harness prevents database/network access during evaluation.

The separate frozen adversarial-v1 report challenges these rules without engine tuning. Review its semantic, direct-ownership, recency and preference-conflict failures before connecting a provider. No production rollout is certified.
