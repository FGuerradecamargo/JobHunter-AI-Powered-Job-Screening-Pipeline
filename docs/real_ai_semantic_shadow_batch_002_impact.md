# Batch 002 Downstream Impact Analysis

## Provenance and limits

Offline analysis on `feature/postgres-migration`, starting from `977096c` with
a clean working tree. No production, network, provider or AI access occurred.

The user reports 12 successful requests / 14 need evaluations, zero retries or
provider failures, all responses accepted, prompt `semantic-support-prompt-v2`,
requested/returned model `gpt-5.6-sol`, and store=false. Those execution facts
were not independently verified against provider logs in this task.

`tests/fixtures/semantic_shadow_batch_002_observed.json` records the normalized
Relation/Coverage pairs reported by the user. It is OBSERVED_REAL_AI history,
not a new gold reference. Unchanged pairs follow the user's explicit statement
that all other judgments matched. REFERENCE is read separately from the frozen
Batch 002 definition, not overwritten by observations.

The supplied summary contains no per-source links, confidence or reason fields.
Consequently this is a deterministic **pair-level sensitivity replay**, not a
claim to reproduce unknown original provider envelopes. Replay constructs fixed
valid source links, known confidence, canonical reason codes and no joint support
for both sides. AV02 uses its separate recovery/release records; AV06 deliberately
reuses recovery for the tax comparison. Other cases use their supplied records.
The links are reconstruction assumptions, not additional real-AI observations.
No request IDs, raw responses, prompts or reasoning traces are stored.

## Method

For every case, both sides pass through existing code:

normalized response -> validate_semantic_support -> semantic_requirement_links
-> build_profile_hiring_case_input -> build_hiring_case.

The comparison includes assessment, evidence constraint and reason, temporal
applicability, blockers, strength, opportunity value/confidence, category,
HowToProve and AddEvidence. Normalization is deterministic; no language matcher,
prompt tuning, new benchmark judgment or production code change is introduced.

Batch 002 is intentionally a minimal semantic fixture: it supplies no opportunity
signals, hard blockers or current-version requirements. With that exact context,
all 12 cases have MEDIUM/LOW-confidence Opportunity Value, VIABLE strength and
SKIP_FOR_NOW category in both replays. "No known blocker" is not a finding that
a real person is legally eligible. Temporal applicability is NOT_APPLICABLE,
not demonstrated current proficiency.

Additional, clearly synthetic sensitivity controls fix Opportunity Value at
HIGH, MEDIUM or LOW, and separately inject a source-backed hard blocker. Both
sides retain identical strength/category/value: HIGH yields WORTH_A_TRY; MEDIUM
and LOW yield SKIP_FOR_NOW; the blocker yields INELIGIBLE regardless of semantics.
These controls are not claimed to be facts of the real batch or real jobs.

## Agreement, not accuracy

- Relation: 10/14 = 71.43%.
- Coverage: 11/14 = 78.57%.
- Exact dual-axis agreement: 9/14 = 64.29%.

These are agreement with reviewed synthetic references, not model accuracy or
statistical evidence about production populations. Cases are not scored/ranked.

## Five divergences

| Need | REFERENCE -> OBSERVED_REAL_AI | Assessment / requirement satisfaction | Strength / category | Impact |
| --- | --- | --- | --- | --- |
| SE14 | ADJACENT/PARTIAL -> DIRECT/PARTIAL | EVIDENCE_MISSING / false unchanged | VIABLE / SKIP_FOR_NOW unchanged | EXPLANATION_ONLY |
| SE18 | ADJACENT/FULL -> ADJACENT/PARTIAL | TRANSFERABLE / true -> EVIDENCE_MISSING / false | VIABLE / SKIP_FOR_NOW unchanged | PRODUCT_DECISION_CHANGE |
| SE19 | ADJACENT/PARTIAL -> NONE/NONE | EVIDENCE_MISSING / false unchanged | VIABLE / SKIP_FOR_NOW unchanged | EXPLANATION_ONLY |
| SE44 | ADJACENT/PARTIAL -> DIRECT/PARTIAL | EVIDENCE_MISSING / false unchanged | VIABLE / SKIP_FOR_NOW unchanged | EXPLANATION_ONLY |
| AV02 release | ADJACENT/PARTIAL -> NONE/NONE | EVIDENCE_MISSING / false unchanged; DIRECT_REQUIRED remains unmet | VIABLE / SKIP_FOR_NOW unchanged | EXPLANATION_ONLY |

EXPLANATION_ONLY denotes changed retained semantic detail, not a claim that the
current production UI displays this shadow output. Current HowToProve and
AddEvidence contracts are byte-equivalent as serialized for these four cases.
SE14/SE44 change correspondence wording without turning partial into full.
SE19/AV02 lose the retained adjacent partial-support link, which matters to a
future "complete missing scope" versus "build/add evidence" explanation.

SE18 is a product decision change at the evidence/action level even though its
final category does not change. Reference proof retains e0, is interview-defensible
and satisfies DEFENSIBLE. Observed PARTIAL is EVIDENCE_MISSING, loses proof refs
in the legacy requirement projection, is not interview-defensible, changes
HowToProve to evidence clarification and creates an AddEvidence question.
Partial support still survives in the full semantic result. Both states are
non-PROVEN CORE evidence, so existing strength rules return VIABLE in either case.

SE18's multinational-versus-local scale distinction needs human adjudication
against the reviewed scale-separation policy before adopting observed output as
product authority. This analysis does not reverse the human ADJACENT/FULL ruling
or add a second scale penalty. No scope gate was inferred from wording.

The other seven cases (SE03, SE04, SE13, SE40, SE55, AV06, AV26) have
NO_PRODUCT_IMPACT in this comparison. AV06 recovery remains PROVEN and tax
EVIDENCE_MISSING. SE55 remains missing independence proof, not GAP. There are
14 needs in total because AV06 and AV02 each contain two needs.

## Safety impact

Within the reconstructed pairs and fixed contexts, no observed output:

- promotes a previously unsupported requirement to PROVEN;
- newly satisfies DIRECT_REQUIRED;
- turns missing evidence into a confirmed GAP;
- bypasses the injected hard blocker;
- improves eligibility, Hiring Case Strength or final category without support.

Opportunity Value is unchanged, as its separate inputs are held constant.
The only satisfaction change is conservative (SE18: satisfied -> unsatisfied).
This is not evidence that arbitrary AI outputs are safe or that the batch tested
real eligibility/temporal edge cases. Existing constraint/authority tests cover
those boundaries; original per-link outputs would be needed for an exact
forensic replay rather than this bounded sensitivity analysis.

## Human decisions and Alpha

Human review should resolve SE18 before promoting this interpreter into decision
authority, and SE19/AV02 before using its semantic links for evidence guidance.
SE14/SE44 warrant explanation-level correspondence review, not an emergency
classification fix. None of the five is a demonstrated optimistic safety breach.

Another live semantic batch is **not required before Private Alpha on the basis
of these results**, provided the adapter remains non-authoritative shadow and
the existing deterministic safety boundaries remain enforced. Another sample
would not resolve a human contract interpretation by itself. A production
integration decision requires separate approval, these human adjudications and
targeted validation of the intended explanatory behavior. No Batch 003 is created.

## Files and verification

Only this document, `tests/fixtures/semantic_shadow_batch_002_observed.json`,
`tests/semantic_shadow_batch_002_replay.py` and
`tests/test_semantic_shadow_batch_002_impact.py` are added.
No reviewed reference, prompt v2, model settings, engine, mapping or UI changes.

Focused replay/engine/evidence constraint/semantic boundary tests: 158 passed.
The engine suite includes Opportunity Value and category classification tests.
The replay includes fixed-value and hard-blocker sensitivity checks.

Full suite: **1668 passed, 2 skipped**, 72.30 seconds. Network connections and
DNS were blocked, with isolated test database fixtures. No external calls,
production access, commit or push. Tracked and new-file whitespace checks passed.
