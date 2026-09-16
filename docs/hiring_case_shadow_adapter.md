# Hiring Case V1: local shadow adapter

This slice is computation-only. `evaluate_hiring_case_shadow(source)` accepts an
already loaded `ApplicationAnalysisSource`, runs the deterministic adapter and V1
engine, and returns a non-authoritative comparison. It neither runs legacy
analysis nor loads/saves anything. No page, production analysis service, ranking,
CV generator, interview preparation flow, or repository calls it yet.

## Inputs and boundaries

`HiringCaseShadowSource` contains the existing Candidate, ApplicationAnalysisSource,
optional JobProfile and CareerObjective, and existing CareerUpdates. These are
source facts used by Career Memory; interpreted memory narratives are not proof.
Candidate/job/profile/objective/update identities must agree. The caller must
load these under the existing authenticated candidate boundary; this pure local
function does not authenticate users. Scope mismatch raises a static exception.

An analysis ID and nonempty legacy analysis are required. If neither JobProfile
nor the legacy parsed core requirements provide core needs, the shadow abstains
with `core_requirements_missing`. This prevents the V1 engine's empty-core list
from producing a vacuously strong case. An existing hard blocker still produces
INELIGIBLE even when core requirements are absent.

## Requirement extraction

| Existing field | Importance |
| --- | --- |
| JobProfile.must_have_capabilities / must_have_experience | CORE |
| JobProfile.required_qualifications / structural_requirements | CORE |
| JobProfile.key_responsibilities / tools_and_technologies | IMPORTANT |
| JobProfile.nice_to_have | NICE_TO_HAVE |
| Legacy analysis.core_requirements, only when the profile has no core labels | CORE |

Duplicate labels retain the highest importance. Whitespace, case and trailing
sentence punctuation are normalized for equality. Requirement IDs are stable
hashes of these keys. There is no substring matching, token similarity, synonym
inference, new NLP, or use of current_fit/growth_value. Lists are ordered
deterministically. Responsibilities and tools are conservatively important unless
the same label is explicitly core; their real materiality may need review.

Evidence references reuse `build_application_evidence`. PROVEN requires an exact
label from professional experience with an existing source_experience_id.
TRANSFERABLE uses an exact recorded transferable capability; the professional
experience `transferable_capability` metadata remains transferable despite the
older evidence builder assigning it professional_fact authority. A transferable
profile entry without a concrete experience remains not interview-defensible.

Profile skill/proven lists alone, developing capability, free-form updates,
legacy requirements_met/strengths/structural_gaps and missing source IDs do not
establish direct proof. They remain EVIDENCE_MISSING. Paraphrased true evidence
will often be missed: the adapter deliberately abstains from semantic matching.

The existing models lack a verified requirement-level absence/insufficiency flag.
For local reviewed fixtures, an optional `ConfirmedCapabilityGap` explicitly binds
candidate, job, requirement and an existing career update. The caller must have
reviewed that update as confirmation of insufficient capability. The adapter
checks scope and existence, but cannot verify the meaning of its prose. This is
a trusted caller contract, not a new user endpoint or automatic interpretation.
Without confirmation, no GAP is inferred from silence, learning goals or AI gaps.
Contradictory confirmation and supporting proof become EVIDENCE_MISSING pending
review. Confirmation provenance stays in the input; it is not put into positive
experience references or included in diagnostic output.

## Opportunity value

All nine V1 dimensions are emitted, initially UNKNOWN. Exact role-family matching
uses the existing role_family_key aliases. An active objective's structured desired
families take precedence over candidate targets; otherwise candidate target
families or exact canonical target roles can establish positive career direction.
A nonmatch is unknown, not proof of an unwanted role.

An exact responsibility match with an active candidate priority gives positive
IMPORTANT role content or negative CORE role content. Negative takes precedence
when both are recorded. A single unambiguous remote/hybrid/onsite work condition
that is explicitly disallowed yields a negative IMPORTANT work-mode signal.
`remote=False` does not imply onsite. Being allowed alone does not establish
personal value. Conflicting modes remain unknown.

Salary is currently a string; the candidate minimum has no common currency/period
contract. Compensation stays UNKNOWN even for plausible salary strings. Benefits,
culture, stability, strategic value, growth, location compatibility and timing are
not invented. Seniority labels and level_assessment prose do not establish a
verified mismatch/progression relation, so no mismatch is inferred. Existing
hard_conflicts or rule_rejection_type=hard_filter remain upstream blockers.

The V1 semantic rules are unchanged. Unknown dimensions lower confidence, not
value. In particular this engine can report HIGH value from one positive known
dimension with MEDIUM confidence: that is existing V1 policy, not a quality claim
about the evidence sample.

## Comparison and diagnostics

`HiringCaseShadowComparison` includes:

- schema_version=hiring-case-v1, comparison_schema_version=hiring-case-shadow-v1,
  adapter_version=hiring-case-input-adapter-v1, authoritative=false;
- allowlisted legacy_value and shadow_classification;
- comparison: same, different, unmapped or not_evaluated;
- hiring_case_strength, opportunity_value and opportunity_confidence;
- proven_count, transferable_count, evidence_missing_count, gap_count,
  core_gap_count and needs_evidence_count;
- a static unavailable_reason when computation must abstain.

Equality is semantic through the existing legacy compatibility map, so potential
and WORTH_A_TRY compare as same. The existing map has no reject equivalence; reject
remains unmapped, not silently equated with SKIP_FOR_NOW or INELIGIBLE. Unknown
legacy strings become the fixed `unknown` marker and are never logged verbatim.

The INFO log event `hiring_case_shadow` serializes only that internally built
comparison. No IDs, names, titles, rationale, evidence refs/text, CVs, notes,
prompts, source dictionaries or exception details appear. Legacy objects are
unchanged, including recommendation/bucket and analyses without shadow metadata.

## Local fixture harness

`compare_hiring_case_fixtures(sources)` returns aggregate counts and transitions.
Its inputs must already contain legacy analyses. The synthetic fixture variations
in tests/hiring_case_shadow_fixtures.py reuse the existing Application Contract
candidate/analysis fixtures. They are scenario coverage, not a measured production
accuracy sample. No fixture contains live candidate data.

Expected eight-scenario summary:

- total/evaluated: 8/8; same: 3; changed: 4; unmapped: 1; not_evaluated: 0;
- best_match -> best_match: 1; best_match -> youre_strong_but: 1;
- potential -> best_match: 1; potential -> worth_a_try: 2;
- good_opportunity -> best_match: 1; competitive -> worth_a_try: 1;
- reject -> ineligible: 1 (unmapped);
- evidence_missing total/average: 1/0.125; core gaps total/average: 1/0.125.

Averages use evaluated rows only. Same + changed + unmapped + not_evaluated equals
total. An empty/unevaluable sample reports zero averages, with evaluated=0 to avoid
implying complete evidence. Reordering fixtures does not change the aggregate.

## Persistence and next step

No schema or persistence was added: local fixture computation is sufficient to
validate the adapter boundary. A future opt-in integration can compute this after
an existing completed analysis and attach only comparison metadata to a dedicated
non-authoritative field, but that is not enabled here. Historical analyses must
not be rewritten. First expand reviewed anonymized fixtures to validate exact
requirement/evidence links and gap confirmations; then consider that integration.
