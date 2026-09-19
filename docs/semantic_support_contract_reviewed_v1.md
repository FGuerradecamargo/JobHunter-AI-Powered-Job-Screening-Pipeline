# Semantic Support Contract - Reviewed V1

Authority: explicit human product review following the Batch 001 and qualifier
audits. This freezes product meanings and selected synthetic judgments, not a
claim that all historical references constitute independent human gold.
Contract revision: `semantic-support-reviewed-v1`.
Benchmark revision: `semantic-evidence-v1-reviewed-1` (55 cases).

## Relation

Question: how directly does the demonstrated capability correspond to the
required capability?

- DIRECT: substantially the same capability/work is demonstrated.
- ADJACENT: meaningfully transferable capability differs in a relevant domain,
  environment, context, scale, responsibility level, or other dimension.
- NONE: no material support for the capability in the supplied evidence.
- UNCERTAIN: facts are insufficient or conflicting, so the relationship cannot
  be established safely.

Relation is not a count of fulfilled requirement components. A record can
directly demonstrate investigation without establishing required approval.

## Coverage

Question: how much of the explicit material scope of this requirement is
supported?

- FULL: all explicit material facets are supported.
- PARTIAL: at least one material facet is supported and at least one is not
  established.
- NONE: no material facet is supported.
- UNKNOWN: completeness cannot be established safely.

Coverage is NOT a similarity score. Explicit independently, own/ownership,
authorize, approve/approval authority, final decision, signoff, accountability,
and equivalent responsibility language are material when required by the need.
Equivalent factual actions can establish them; literal keyword repetition is
not necessary. No keyword matcher, inferred facet schema, or new enums exist.

## Distinct deficiencies, not duplicate penalties

One factual mismatch must not automatically lower both relation and coverage.
Complete scheduling-incident work in retail versus hospital context is normally
ADJACENT/FULL. The domain difference changes correspondence, not demonstrated
functional completeness. An independently stated domain-specific action could
still be unsupported; do not invent one.

Actual complete work in another environment may likewise be ADJACENT/FULL.
Lab execution is not theory-only course attendance. A context difference need
not matter at all when the requirement is context-neutral (volunteer logistics).

Two distinct deficiencies may affect separate axes: simulated payroll delivery
is adjacent to professional delivery, while missing required ownership makes
coverage partial. SE13 is ADJACENT/PARTIAL, not NONE/NONE. Practical execution
must not be erased merely because it happened in a project.

Scale retains the existing independent Hiring Case scope gate. Do not derive
PARTIAL automatically from a scale fact already represented by that gate.
AV17/AV19 keep task proof and scope_mismatch=True, producing WEAK globally.
Distinct explicit missing task facets may still warrant partial support. The
current Boolean gate has no automated deduplication mechanism; none is added.

## Missing proof is not confirmed absence

The technical task can be demonstrated while independent execution is unknown.
SE55 isolates this: DIRECT/PARTIAL, aggregate EVIDENCE_MISSING, not GAP.
The candidate may have worked independently; the evidence does not prove it.
Only authoritative source-backed confirmed absence permits existing GAP logic.
Conflicting positive/absence sources remain uncertain rather than choosing the
favorable statement. Titles, source provenance, and checkpoints are not proof.

## Mapping, unchanged

| Relation / coverage | Aggregate requirement assessment |
| --- | --- |
| DIRECT/FULL | May support PROVEN, subject to existing safeguards |
| ADJACENT/FULL | May support TRANSFERABLE |
| DIRECT/PARTIAL or ADJACENT/PARTIAL | EVIDENCE_MISSING |
| NONE/NONE | EVIDENCE_MISSING unless independent confirmed absence authorizes GAP |
| UNCERTAIN/UNKNOWN | EVIDENCE_MISSING / abstention |

Partial links and supporting_refs survive in ResolvedSemanticSupport. The
legacy semantic_requirement_links projection only forwards proof refs for
PROVEN/TRANSFERABLE; consumers must retain the complete semantic result to keep
partial-support detail. No production mapping was changed.

The existing boundary permits DIRECT/ADJACENT with FULL/PARTIAL, NONE/NONE,
and UNCERTAIN/UNKNOWN; it does not permit every Cartesian pair, such as
DIRECT/UNKNOWN. No schema change is made by this conceptual clarification.
Multiple sources require explicit complementary joint support, not reference
counting, to establish FULL. Structural validation cannot verify semantic truth.

DIRECT_REQUIRED remains independent. In AV02, release communications give
ADJACENT/PARTIAL and EVIDENCE_MISSING; the explicit direct constraint is still
unsatisfied with reason direct_evidence_required. As an IMPORTANT incomplete
need it produces VIABLE, not two additive penalties. Core recovery stays
PROVEN; final outcome remains VIABLE/HIGH/WORTH_A_TRY.

Temporal applicability also remains separate, using authoritative change/version
facts, not age heuristics. SE35 retains historical adjacent support and the
unsatisfied current-procedure boundary. No temporal or scope gate is removed.

## Reviewed changes and fixture history

Three categories are deliberately separate:

### A. Synthetic fact corrections

- NeedFacts default evidence gains exactly the independence fact:
  `Independently traced a failed payment, isolated the cause, restored service and verified settlement.`
  The need remains `Resolve payment incidents independently`.
- This changes 25 adversarial cases' facts: 22 use shared P directly; AV04,
  AV21, AV31 inherit the same evidence through separate constructors. Their
  provenance/authority rejection behavior remains intact. AV01/AV18 now have
  independence in the actual selected evidence, not only contextual assertions.
- HC02b now explicitly owns independent disputed-purchase investigations while
  retaining the adjacent fraud-domain bridge. HC18a now explicitly independently
  leads the described allocation/coaching/recovery, without claiming an already
  held formal team-lead title. Both original expected outcomes remain unchanged.
- AV26's structured need becomes `Own production recovery`, aligning it with
  its stated production-responsibility scenario. Sandbox evidence is unchanged.

Total fact-affected cases: 28 (25 defaults, AV26, two HC). Of these, **26 have
fact corrections only**; AV02 and AV26 also have reviewed judgment changes.
The number is not 26 distinct new product decisions. Shared P alone has 22
users, 21 expected PROVEN and one expected safe rejection (AV32).

### B. Human reference judgment changes

| Case | Original | Reviewed | Why |
| --- | --- | --- | --- |
| SE04 | ADJACENT/FULL/TRANSFERABLE | ADJACENT/PARTIAL/EVIDENCE_MISSING | Updates under commander do not establish command ownership |
| SE13 | ADJACENT/FULL/TRANSFERABLE | ADJACENT/PARTIAL/EVIDENCE_MISSING | Practice exists, professional ownership not established |
| SE14 | ADJACENT/FULL/TRANSFERABLE | ADJACENT/PARTIAL/EVIDENCE_MISSING | Assistance does not establish independence |
| SE40 | ADJACENT/PARTIAL/EVIDENCE_MISSING | NONE/NONE/EVIDENCE_MISSING | Attendance/notes do not materially demonstrate audit signoff |
| SE44 | ADJACENT/FULL/TRANSFERABLE | ADJACENT/PARTIAL/EVIDENCE_MISSING | Options prepared; executive owns allocation decision |
| AV02 release | TRANSFERABLE | ADJACENT/PARTIAL/EVIDENCE_MISSING | Release communications do not establish required direct ownership |
| AV26 | TRANSFERABLE | ADJACENT/PARTIAL/EVIDENCE_MISSING | Real sandbox practice, production ownership not established |

SE03 and SE18 remain ADJACENT/FULL. SE19 remains ADJACENT/PARTIAL: transferable
troubleshooting exists, but backend production diagnosis is unsupported. AV06
keeps recovery DIRECT/FULL and tax NONE/NONE using the corrected recovery fact.
No other adversarial expected state or final product outcome changes. AV02 and
AV26 remain VIABLE/HIGH/WORTH_A_TRY. All 40 calibration judgments are preserved.

### C. New regression, not repurposed AV06

SE55: `Resolve payment incidents independently` with the exact original E0:
`Traced a failed payment, isolated the cause, restored service and verified settlement.`
Reviewed result: DIRECT/PARTIAL/EVIDENCE_MISSING, confirmed_absence=false.
It captures the useful Batch 001 discovery without contaminating AV06's
unrelated-evidence-reuse purpose or compensation/timing/eligibility controls.

## History and freezes

The original 54-case reference is preserved byte-for-byte after LF normalization
in `tests/fixtures/semantic_evidence_v1_original_reference.json`. The review
ledger `tests/semantic_contract_review_v1.json` preserves prior freeze hashes,
original changed case definitions and every original HC/AV expected judgment.
Tests reconstruct the prior full case freezes and constrain changes to the
authorized sets. Current freeze hashes and the two affected calibration source
signatures are intentionally renewed, not silently bypassed. Earlier temporal
history keys remain; a separately named current excluding-AV28 hash is added.

Batch 001 remains historical: it used the old ambiguous AV06 evidence and
returned DIRECT/PARTIAL. Its original SE13 reference was ADJACENT/FULL and
observed NONE/NONE. The batch review, usage, request IDs, signatures and earlier
audits are unchanged. Their reconstructed-input statements describe the code
and fixtures at that time, not today's revised selection. The original
first-batch manifest is a preparation artifact, not a new execution log.
Future selections use the reviewed reference and corrected AV06 input and
must never be presented as rerunning identical Batch 001 facts.

## Offline interpretation and future use

Controlled replies mean "suppose an interpreter supplied the reviewed
relationship". They are updated for the five changed SE cases and SE55, with
explicit AV02/AV26 semantic regression overlays. They are not an NLP model or
benchmark accuracy improvement. No live call, prompt change, schema change,
production engine change, or UI implementation accompanies this revision.

Future Career Journey semantics, not implemented labels:
NONE -> BUILD / ADD EVIDENCE; ADJACENT/FULL -> BRIDGE / TRANSFER;
partial -> COMPLETE MISSING SCOPE; DIRECT/FULL -> PROVEN / MAINTAIN;
UNCERTAIN -> CLARIFY / REVIEW.

Proposed Batch 002 coverage, not authorized or executed here: SE03, SE04,
SE13, SE14, SE18, SE19, SE40, SE44, SE55, corrected AV06, AV02, AV26.
This is a proposed evaluation set, not a request budget. The current harness
still restricts its original eight case IDs; expanded selection needs separate
authorization and preflight. Its prompt remains unchanged, so it is not yet a
fully updated operationalization of this reviewed contract. Do not launch
Batch 002 until that gap and the case list/budget receive explicit approval.

## Change inventory

Modified in this revision:

- `docs/semantic_evidence_applicability_v1.md`
- `tests/hiring_case_adversarial_cases.py`
- `tests/hiring_case_calibration_cases.py`
- `tests/hiring_case_review_freeze.json`
- `tests/semantic_evidence_v1_freeze.json`
- `tests/semantic_evidence_v1_reference.json`
- `tests/semantic_evidence_v1_replies.json`
- `tests/structured_calibration_fixtures.py`
- `tests/test_hiring_case_evidence_constraints.py`
- `tests/test_semantic_evidence.py`
- `tests/test_temporal_applicability.py`

Added in this revision:

- `docs/semantic_support_contract_reviewed_v1.md`
- `tests/fixtures/semantic_evidence_v1_original_reference.json`
- `tests/semantic_contract_review_v1.json`
- `tests/test_semantic_contract_review.py`

Earlier uncommitted adapter, harness, preparation manifest, Batch 001 review,
contract review and qualifier audit files are preserved unchanged. No source
under `services`, `models`, `pages` or `scripts` was edited in this revision.

## Offline validation

- Focused semantic/review/calibration/temporal/fake-adapter tests: 298 passed.
- Expanded semantic, engine, profile, Career Memory, CV, interview and auth
  regression: 765 passed. An old AV02 TRANSFERABLE assertion was aligned with
  the reviewed EVIDENCE_MISSING state; direct constraint assertions remain.
- Full suite: 1608 passed, 2 skipped (244.48 seconds).
- Socket connections and DNS resolution were blocked for these runs; test
  database isolation disabled PostgreSQL access. Zero external calls and no
  production access. No live harness execution, commit or push.
