# Semantic evidence applicability v1

## Scope and authority

Shadow-only, provider-neutral, in-memory contract. No production UI, database,
provider integration, scoring change or Career Memory mutation is introduced.
Existing uncommitted evidence constraints, temporal applicability, calibration,
onboarding and Career Journey work is preserved.

VALID PROVENANCE IS NOT SEMANTIC SUPPORT. The trusted source registry establishes
ownership, source class and availability. It cannot determine whether an office
lunch rota supports incident recovery. A semantically false DIRECT/FULL response
with valid references can still pass structural checks. A regression test records
this limitation rather than claiming offline language understanding.

## Contract

`SemanticSupportRelation`: DIRECT, ADJACENT, NONE, UNCERTAIN.
`SemanticCoverage`: FULL, PARTIAL, NONE, UNKNOWN. These are separate from the
existing PROVEN / TRANSFERABLE / EVIDENCE_MISSING / GAP assessment states.

Each `SemanticEvidenceLink` identifies one need, evidence reference, optional
profile capability, relation, coverage, confidence, reason code, interpreter
version and source-fact authority. No new experience, ownership, tools, dates,
outcomes or chain-of-thought fields are accepted. Unknown JSON fields fail closed.
There is no required prose explanation. A question hint on the aggregate result
is private, non-authoritative and never promotes state or modifies source data.

`NeedSemanticSupport` retains each relationship and an explicit aggregate
relation/coverage judgment. `SemanticSupportRequest` binds the current candidate
and job profiles, versions, hard facts, registry and authorized source content.
The full canonical request signature includes source text and profile content,
not just IDs. Unknown, foreign, checkpoint and stale references fail closed.
The signature detects changed inputs; it is not cryptographic source authentication.
Source authenticity remains the responsibility of the trusted caller/source layer.

The `SemanticSupportInterpreter.evaluate_semantic_support` protocol is the future
adapter interface. Responses must pass `validate_semantic_support`; callers must
not treat raw provider responses as accepted assessments. The fixture adapter is
exact-key, deep-copied and returns UNAVAILABLE for missing interpretations. There
is no OpenAI adapter, fallback semantic classifier or network operation here.

## Resolution

* DIRECT/FULL can support PROVEN; ADJACENT/FULL supports TRANSFERABLE.
* PARTIAL cannot prove an indivisible requirement. It remains EVIDENCE_MISSING,
  retaining the real source links and partial support in the semantic result.
* NONE and UNCERTAIN cannot prove a requirement. NONE alone does not create GAP.
* A source-backed confirmed absence permits GAP. Conflicting support/absence
  remains uncertain, without choosing the favorable source.
* Unknown confidence and explicit conflicting sources preserve uncertainty.
* A transferable capability cannot be promoted by omitting its optional ID.
* Explicit DIRECT_REQUIRED remains independent: ADJACENT evidence remains
  TRANSFERABLE, while the existing engine reports the direct constraint unmet.
* Current-proficiency claims are capped at TRANSFERABLE when temporal applicability
  is NOT_SATISFIED or UNKNOWN. Historical evidence is preserved. There is no age
  threshold, clock, or text-based procedure detection.

The engine/quadrant policy is unchanged. `semantic_requirement_links` revalidates
the raw response and projects only complete qualifying support into the existing
adapter. Keep the full semantic result alongside that projection: partial evidence
must not be treated as full proof merely because its source is valid. Existing
profile/temporal metadata must still accompany the domain interpretation.

## Compound and multiple-source support

There is no existing structured facet contract on Job Profile, so this v1 uses
whole-need PARTIAL coverage. It deliberately rejects invented facet identifiers;
it does not split requirements by keywords or introduce an NLP decomposer.

Multiple refs alone never imply FULL. An interpreter must explicitly declare
JOINT_SUPPORT for complementary partial sources. At least two distinct supporting
relationships are required; unknown/unsupported constituents cannot supply the
missing part. A single partial source cannot become FULL by setting the joint flag.
Whether two real sources genuinely complement each other is a semantic judgment,
not something the validator can independently establish. A future structured facet
contract could improve auditing of that judgment without adding prose heuristics.

Evidence reuse is allowed across needs. Each selected evidence/need pair is
evaluated separately. Unrelated reuse fails when the semantic interpreter reports
NONE; changing IDs or globally banning reuse is not the solution. The boundary
also cannot detect a provider omitting a relevant contradictory source. Source
selection and semantic truth require independent human-reviewed shadow evaluation.

## Future product use

The retained structure distinguishes absent, adjacent, partial, direct and uncertain
support. Career Journey can later suggest Build, Bridge, Complete, Maintain or
Review; those UI labels are not persisted in this contract. Partial question hints
can target missing approval authority without erasing known investigation work.
Hints are never evidence or automatic Career Memory updates. P0 low-friction
voice/text onboarding and Career Journey TODOs remain documentation only.

## Evaluation design

`semantic-evidence-v1` contains 54 synthetic product-reference proposals: 50
interpretable cases and four authority rejection cases. References were authored
and SHA-256 frozen before boundary implementation/execution. Tests verify the
freeze with LF normalization. Runtime projection cannot read expected judgments.
Controlled replies are stored separately and provided explicitly, not inferred
from source text. Expected judgments were not changed after running the tests.

This is a separate dataset, not an independent human-reviewed gold set. References
and replies share authorship and were deliberately aligned for contract testing;
their agreement is NOT AI accuracy or statistically blind semantic evaluation.
The scenario distribution tests coverage, not labor-market frequency.

The original 40 and adversarial-v1 reference definitions/hashes remain unchanged.
The original adversarial run still reports the three semantic failures. Separate
AV05/AV06/AV27 shadow fixtures demonstrate their resolution when a future semantic
interpreter supplies the right relationship; they do not make the old hostile
responses magically correct.
