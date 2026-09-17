# Adversarial v1: frozen offline evaluation

Agent-authored proposed judgments, not an independent human-reviewed gold set. Expectations and
controlled replies were initially frozen before execution. AV28 alone was subsequently updated by
explicit human product review: historical support is TRANSFERABLE, not missing. Same-author design
cannot establish statistically blind or real-world AI accuracy. The hardening pass adds explicit
evidence constraints and unresolved preference-source conflicts. Only the authorized AV28 review
changes the previously frozen expectation and controlled semantic relation.

Cases: 32. Agreements (safe rejection included): {'classification': 29, 'strength': 29, 'value': 32, 'confidence': 32}.
Evidence: 33/36. Safe rejections: 2.
Mismatch taxonomy: {'semantic_entailment': 3}.

Explicit evidence constraints: 1/1 (AV02).
Rejected cases do not receive a category; they are reported as not_evaluated. Evidence denominators
exclude the two rejection expectations, not silently treat them as successful evidence assessments.

| Case | Scenario | Expected category | Observed category | Mismatches | Root cause |
| --- | --- | --- | --- | --- | --- |
| AV01 | several important bridges | best_match | best_match | none | none |
| AV02 | explicit direct ownership constraint | worth_a_try | worth_a_try | none | none |
| AV03 | multiple peripheral gaps | best_match | best_match | none | none |
| AV04 | broken source | worth_a_try | worth_a_try | none | none |
| AV05 | irrelevant valid evidence | worth_a_try | best_match | classification, strength, states | semantic_entailment |
| AV06 | unrelated evidence reuse | worth_a_try | best_match | classification, strength, states | semantic_entailment |
| AV07 | strong but poor value | youre_strong_but | youre_strong_but | none | none |
| AV08 | weak but attractive | worth_a_try | worth_a_try | none | none |
| AV09 | unknown salary | youre_strong_but | youre_strong_but | none | none |
| AV10 | below target | youre_strong_but | youre_strong_but | none | none |
| AV11 | above target | best_match | best_match | none | none |
| AV12 | acceptable hybrid unknown commute | best_match | best_match | none | none |
| AV13 | unacceptable known commute | youre_strong_but | youre_strong_but | none | none |
| AV14 | urgent lateral bridge | best_match | best_match | none | none |
| AV15 | stable lateral distraction | youre_strong_but | youre_strong_but | none | none |
| AV16 | overqualified | youre_strong_but | youre_strong_but | none | none |
| AV17 | underqualified scale | worth_a_try | worth_a_try | none | none |
| AV18 | different title equivalent scope | best_match | best_match | none | none |
| AV19 | impressive title insufficient scope | worth_a_try | worth_a_try | none | none |
| AV20 | explicit hard blocker | ineligible | ineligible | none | none |
| AV21 | implied condition not blocker | not_evaluated | not_evaluated | none | none |
| AV22 | direction conflict | youre_strong_but | youre_strong_but | none | none |
| AV23 | secondary accepted direction | best_match | best_match | none | none |
| AV24 | course without practice | worth_a_try | worth_a_try | none | none |
| AV25 | practice not defensible | worth_a_try | worth_a_try | none | none |
| AV26 | project versus professional | worth_a_try | worth_a_try | none | none |
| AV27 | partial requirement | worth_a_try | best_match | classification, strength, states | semantic_entailment |
| AV28 | recency required | worth_a_try | worth_a_try | none | none |
| AV29 | unknown preference | youre_strong_but | youre_strong_but | none | none |
| AV30 | contradictory preferences | youre_strong_but | youre_strong_but | none | none |
| AV31 | job profile uncertain | worth_a_try | worth_a_try | none | none |
| AV32 | checkpoint self confirmation | not_evaluated | not_evaluated | none | none |

## Interpretation

Valid refs alone cannot certify semantic relevance or complete coverage. Reuse across unrelated
needs is structurally possible; a semantic evaluator must reject the wrong relationship. Explicit
direct-ownership requirements now use source-backed DIRECT_REQUIRED, independently of IMPORTANT.
AV02 becomes VIABLE without changing TRANSFERABLE evidence. AV30's two explicit, equally current
preference sources now force UNKNOWN; no winner is selected. Semantic support failures remain visible.

AV28 now has an explicit source-backed current-procedure requirement, a superseded procedure
version on its historical source, and the reviewed TRANSFERABLE semantic link. Applicability is
NOT_SATISFIED while evidence remains valid. No age threshold, clock or prose matcher is used.
Its expected state and controlled semantic reply changed only under explicit human review; the
other 31 cases and the original 40-case calibration are protected by their existing hashes.

Confidence is coarse: HIGH requires all signals known, MEDIUM means mixed, LOW means all unknown.
An additional unknown fact may not lower an already MEDIUM bucket. Marginal confidence and
materiality weighting require a separate reviewed policy; UNKNOWN never becomes negative here.
