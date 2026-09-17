# Semantic evidence v1: contract/reference evaluation

## Integrity and interpretation

54 independent scenario definitions, including 50 accepted/normalized examples and
four safe authority rejections. Synthetic product-reference proposals pending human
review, NOT an independently human-reviewed gold set or real-world AI accuracy.
Reference SHA-256 (LF normalized):
`c9a501a2b94969612320d1ad3606fbea8fc83ddb1f0a6cd589934e5f165e16b9`.

Reference judgments were frozen before implementation/execution and unchanged
after testing. Controlled replies are deliberately aligned with those authored
judgments. This measures a contract consuming supplied semantic interpretations,
not an independent model predicting them. Runtime projection/evaluation cannot
read expected judgments until the comparison stage. No semantic text heuristic,
embedding, provider, production database or UI was used.

## Agreement

| Measure | Accepted denominator | Including safe rejection expectations |
| --- | --- | --- |
| Relation | 50/50 | 54/54 |
| Coverage | 50/50 | 54/54 |
| Aggregate Hiring Case assessment | 50/50 | 54/54 |

Aggregate assessments also pass through the existing profile Hiring Case adapter;
they are not merely echoed from the semantic response. Rejections have no assessment.

| Reference relation | Cases | Relation / coverage / assessment agreement |
| --- | --- | --- |
| DIRECT | 18 | 18/18 for each |
| ADJACENT | 15 | 15/15 for each |
| NONE | 10 | 10/10 for each |
| UNCERTAIN | 7 | 7/7 for each |

| Reference coverage | Cases | Relation / coverage / assessment agreement |
| --- | --- | --- |
| FULL | 24 | 24/24 for each |
| PARTIAL | 9 | 9/9 for each |
| NONE | 10 | 10/10 for each |
| UNKNOWN | 7 | 7/7 for each |

## Authority and overclaim probes

Benchmark rejects: foreign candidate scope 1/1, checkpoint ref 1/1, unknown ref 1/1,
stale input 1/1. These are the four safe rejections, not four failed predictions.

Separate focused mutation tests (not added to the benchmark denominator) establish:

* Unknown, checkpoint and job-as-candidate refs: 3/3 rejected.
* Unsupported ownership promotion: 1/1 capped at TRANSFERABLE.
* Single-source partial-to-full overclaim: 1/1 capped at EVIDENCE_MISSING.
* Unsupported cross-need reuse against declared NONE: 1/1 capped at EVIDENCE_MISSING.
* Omitting capability ID cannot hide a transferable profile restriction.
* Legitimate reuse of one source for two independently supported needs is accepted.
* Explicit joint interpretation permits complementary evidence; source count alone
  cannot promote partial evidence. Duplicate relationships fail closed.
* Source conflicts remain uncertain, regardless of order. Question hints do not
  change source memory or evidence states. Logs contain only status/codes/counts.

These probes detect contradictions in structured claims, NOT a semantically false
but structurally coherent provider interpretation. The latter remains intentionally
demonstrated by a limitation regression test.

## Existing references and targeted shadow execution

Original calibration unchanged: classification 40/40, strength 40/40, Opportunity
Value 40/40, evidence states 46/46. Only the previously designated three original
judgments are human reviewed; the remaining proposals retain their prior status.

Original adversarial-v1 unchanged: 32 total, 30 classified, two safe rejections.
Classification 27/30, strength 27/30, Value 30/30, evidence 33/36. AV05, AV06 and
AV27 remain unresolved when their original hostile replies omit semantic support.

Separate, explicit semantic fixtures produce:

| Case | Relationship | Assessment | Downstream result |
| --- | --- | --- | --- |
| AV05 | valid provenance, NONE/NONE | EVIDENCE_MISSING | VIABLE / HIGH / WORTH_A_TRY |
| AV06 recovery | DIRECT/FULL for recovery ref | PROVEN | VIABLE / HIGH / WORTH_A_TRY overall |
| AV06 tax | same valid ref, NONE/NONE | EVIDENCE_MISSING | VIABLE / HIGH / WORTH_A_TRY overall |
| AV27 | DIRECT/PARTIAL | EVIDENCE_MISSING; investigation preserved separately | VIABLE / HIGH / WORTH_A_TRY |

This is three successful contract/downstream demonstrations, not a claim that the
offline system understood the source prose or repaired the original replies.

## Files in this slice

New:

* `models/semantic_evidence.py`
* `services/semantic_evidence_boundary.py`
* `services/fixture_semantic_interpreter.py`
* `tests/semantic_evidence_v1_reference.json`
* `tests/semantic_evidence_v1_freeze.json`
* `tests/semantic_evidence_v1_replies.json`
* `tests/semantic_evidence_v1_runner.py`
* `tests/test_semantic_evidence.py`
* `docs/semantic_evidence_applicability_v1.md`
* `docs/semantic_evidence_v1_report.md`

Extended only for opt-in semantic shadow fixtures:
`tests/hiring_case_adversarial_runner.py`. Its default run and all frozen expected
answers are preserved. No other pre-existing file was changed in this slice.

## Validation

* Final semantic focused suite: 88 passed.
* Broad authority/profile/engine/Career Memory/CV/interview/auth regression:
  743 passed, 2 skipped before the final additional reuse probe. The final full
  suite below includes that probe and the final downstream adapter projection.
* Final full suite: 1530 passed, 2 skipped in 192.87 seconds.
* Tracked and untracked diff whitespace checks passed; expected LF/CRLF warnings only.
* Production UI diff is empty. Branch remains `feature/postgres-migration`.
* Existing uncommitted work and frozen judgments preserved. No commit or push.
* Tests ran with socket connection/DNS guards and isolated test databases.
  Zero AI, external provider, Gmail, network or production database calls.

## Next step

The contract is ready for a future injected semantic provider adapter in shadow,
not production authority or rollout. First review the proposed semantic references
with a human; then separately authorize a bounded real-AI shadow experiment.
The largest uncertainty is genuine semantic entailment, including source selection,
omitted contradictions and joint coverage. No deterministic matching patch can
settle that uncertainty. No commit or push was performed.
