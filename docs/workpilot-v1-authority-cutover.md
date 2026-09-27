# Phase 14: authority audit and cutover gate

Audit checkpoint: `e978303`, branch `feature/workpilot-v1-implementation`.
This is repository/runtime-call-graph inspection, not a production deployment
attestation. Blocks 1-13 provide contracts and tested components, not a completed
production cutover. No production database, provider, AI, email or browser action
was performed during this audit. The observation WIP was read with `git show`,
not merged or cherry-picked.

## Resolved decision: recommendation visibility with insufficient evidence

The user approved the sufficiency gate after this initial audit. Phase 14 now
implements it in HiringCase v2: relevant evaluations require candidate evidence
refs; missing evidence is not an evaluation; positive support requires PROVEN or
TRANSFERABLE evidence. Zero evaluation is NOT_SURFACED/insufficient_evidence,
never a visible category. Hard incompatibility takes precedence. The original
audit reproduction and decision rationale are retained below as history.

The initial audit found a real product-policy gap before replacing visible search
authority. Eligibility, relationship strength, opportunity value, confidence and
visibility must remain separate. UNKNOWN must not become ineligibility, but that
does not establish sufficient evidence to recommend a job either.

`services/hiring_case_engine.py::determine_hiring_case_strength` falls through to
STRONG when the requirements list is empty. `assess_opportunity_value` returns
MEDIUM/LOW confidence for no signals. `classify_hiring_case` uses strength/value,
not confidence or an explicit sufficiency gate. Result: a visible category despite
zero assessed requirements. `AIJobProfileSnapshot` permits an empty needs tuple;
`AuthoritativeHiringCaseService.evaluate` does not reject that state.

Pure offline reproduction using current production functions:

```python
from models.hiring_case import HiringCaseInput
from services.hiring_case_engine import build_hiring_case

case = build_hiring_case(HiringCaseInput(
    candidate_id="fixture-candidate", job_id="fixture-job", requirements=[]))
# requirements=0, strength=strong, opportunity_value=medium,
# opportunity_confidence=low, classification=youre_strong_but, blockers=0
```

No user data, database or interpreter was involved. This is a concrete gap in the
accepted engine's integration contract, not a claim about any real candidate.

Decision needed: what evidence sufficiency permits surfacing when requirements
or candidate support are unknown? Recommended resolution:

- Empty/unusable Job needs or zero grounded support for CORE/IMPORTANT needs:
  preserve uncertainty and do not surface a recommendation; never INELIGIBLE
  merely for that reason. Retain the job for clarification/reanalysis.
- Partial grounded support, remaining UNKNOWN facts and positive candidate value:
  allow consideration for Worth a Try, with uncertainty shown, without promoting
  missing evidence into strength or proven capability.
- Preserve separate strength/value/confidence. Approve the sufficiency rule before
  changing the classifier or introducing a visibility decision in its existing
  contract. Do not choose an arbitrary score/percentage threshold during wiring.

This changes which jobs a person sees. The initial audit stopped for that decision;
approval has now been supplied. The remaining matrix is a plan, not an assertion
that its production callers have already switched.

## Runtime authority matrix

Actions are exactly KEEP / MERGE / REPLACE / DELETE. They describe the proposed
disposition of the specified responsibility, not unconditional deletion of whole
modules with historical readers. File references are repository-relative.

| Concept | Current runtime authority and evidence | Intended V1 authority | Callers/UI | Legacy/shadow competitor | Action |
|---|---|---|---|---|---|
| Registration/login | `pages/0_Login.py::render_authentication`, `AuthService.register`, Google account/identity services; `session_auth.get_authenticated_user/login_user` validate server sessions and per-context cookies | Same server authentication boundary | `streamlit_app.py`, all authenticated pages | No new V1 authentication architecture needed; module import still invokes bootstrap, not a reason to replace authentication | KEEP |
| Active candidate/admin scope | `user_context_runtime.get_active_user_context`, active-user session/service, `AdminAccessSession`, `AccessPolicy` in shell | Preserve authenticated actor separately from authorized active candidate | Shell, Profile, Opportunities, Sources, app dashboard | Candidate ID supplied by a browser control must not become authorization | KEEP |
| Durable four-question onboarding | `components/profile_onboarding.py` starts `company-interview-v3`; `render_company_interview` routes V3; `company_interview.confirm_text/confirm_voice_transcript/finalize` and `CandidateOnboardingRepository` persist drafts/answers | Existing V3 source-answer contract and confirmed experience lifecycle | Profile onboarding, reload/resume | V1/V2 historical readers are not competing authority | KEEP |
| Candidate evidence to interpreted profile | `CandidateProfileGenerationService.generate` calls legacy prompt/parser and saves `Candidate`; `CareerMemorySourceSnapshot` then serializes that model | Confirmed source answers/experiences -> `SourceEvidence` -> `ProfileInterpretationService` -> versioned `CandidateProfileSnapshot` | `pages/3_Profile.py`, onboarding generation, search candidate adapter | `models/candidate_profile.py`, mutable generated Candidate/Career Memory summaries cannot substitute for confirmed source answers | REPLACE |
| Candidate source projection | `candidate_profile_source.build_candidate_profile_source_evidence` selects `professional_experiences` summaries/evidence from memory payload; those can originate in AI-generated `CandidateProfileGenerationService` output | Same source projection responsibility, but grounded in persisted confirmed answers with stable source/version refs | Currently no production call to official profile interpretation service found | A source-shaped ref must not launder generated summaries into source truth | MERGE |
| Provider ingestion scheduling | `SourceScheduleService` -> `DailyIngestionService` -> configured provider/import path | Retain scheduling/quotas/results; route import writes through one provenance authority | Scheduler command/service, Sources controls | New scheduler/provider implementation is unnecessary | KEEP |
| Gmail/manual/global job writes | `GmailJobProcessor.process_pending_messages` calls `upsert_raw_job` before `add_source`; `JobImportService.import_jobs` does the same | Atomic observation + source association + canonical-authority selection | Sources Gmail/manual import and provider ingestion | `database.upsert_raw_job` still uses longer raw text to authorize overwrites | REPLACE |
| Job identity and private observations | `normalize_observation` namespaces provider IDs; `_canonical_global_id` matches exact URL/title/company/location under source predicates | One conservative global identity/resolution policy; owner-scoped private evidence, public canonical content | Parser, importer, source repository, selector | Independent WIP identity vs Market URL identity; parser IDs must not grant write authority | MERGE |
| JobProfile generation/cache | `JobProfileManager.get_or_create` -> `ai.JobProfileService.create` -> old `models/job_profile.py`; cache uses job signature | `JobHardFacts` -> `ProfileInterpretationService.job_profile` -> versioned `AIJobProfileSnapshot` | `CandidateJobAnalysisService._run_candidate_job_analysis` preparation | Legacy generated must-have lists and mutable cache cannot be official snapshot evidence | REPLACE |
| Hard Filter | `HardFilterAnalyzer.analyze` has been narrowed; runtime passes legacy candidate/profile types | Source-explicit closed-job rules plus finite candidate contradiction checks using V1 structured coverage | Search preparation before buffered recommendation work | Global mandatory Job requirement is not candidate incompatibility | MERGE |
| Candidate x Job relationship | `_run_candidate_job_analysis` invokes `AIRecommendationService.analyze_batch`, persists its recommendation/bucket | Existing `AuthoritativeHiringCaseService` + profile adapter + deterministic engine, after the agreed sufficiency gate | Search/discovery and reanalysis service | Old AI bucket/scoring and `RecommendationEngine` must not decide current V1 results | REPLACE |
| Cooperative search mechanics | `OpportunitySearchRun`, prepared IDs, claims/revalidation and batch max 10 | Same ownership/claims/cancel/buffering orchestration with official relationship outputs | `pages/1_Opportunities.py` | Do not regress to one paid request per job because `ProfileInterpreter.analyze_hiring_case` is presently singular | KEEP |
| Opportunity persistence/categories | `candidate_job_analyses.analysis_json`, activation helpers; Opportunities partitions `best_match/potential/good_opportunity`; `job_analysis_view` labels Potential/Competitive | Persist scoped/versioned HiringCase and explicit surfaced status; display Best Match / Worth a Try / You're Strong, But only when surfaced | Opportunities and job analysis component | Relabeling old buckets is not recomputation; historical `read_legacy_classification` must remain explicitly historical | REPLACE |
| CV context/generation | `build_production_prepare_application_service` -> old ApplicationContract/Context from stored legacy analysis -> generation/repair/guard -> session cache/export | `V1ApplyFlow` using the same Candidate/Job/HiringCase source versions, contextual evidence and strict edit/export guard | Opportunities prepare/preview/download controls | The current factory does not instantiate V1ApplyFlow; its injected preparation service must not independently rebuild a different legacy context | MERGE |
| External apply/confirmation | Opportunities has mark-applied action and company link; `ApplicationLifecycleService` records explicit actions | `V1ApplyFlow.open_external`, defensible READY_TO_APPLY, explicit confirm_applied; safe URL validation | Opportunities, dashboard job cards | URL opening must never imply application submission; current links bypass V1 URL boundary | MERGE |
| Applications/outcomes | `ApplicationOutcomeService/UI` handles explicit outcomes including No Response | Same outcome authority and candidate-job ownership | `app.py::render_application_outcome` | Accepted outcome must not infer mode; age is not rejection/No Response | KEEP |
| Interview rounds/feedback | `app.py::render_interview_preparation` uses legacy single details/feedback/context/preparation services | `InterviewRoundRepository` for sequenced rounds and same-scope feedback; compose current round with verified earlier feedback | Dashboard application cards | Single-row interview storage must become a historical compatibility reader, not overwrite authority for new rounds | REPLACE |
| Company and InterviewBrief | Company registry/source tracking exists; dashboard uses `InterviewPreparationService`, not CompanyProfile/brief composition | `CompanyProfileRepository` public snapshots -> `build_interview_brief` with same application/job/company/round | Future round presentation in existing app | Missing public research provider must be unavailable/partial, not inferred private/company truth | MERGE |
| Global Market | Search `market_position_service` uses candidate analysis batch signals; `CareerIntelligenceSnapshotService` aggregates candidate-derived evidence | Public `MarketJobObservation` -> `build_market_profile` -> `MarketProfileRepository` | Search market panel, future refreshed market projection | Candidate-specific analyses cannot define canonical global Market | REPLACE |
| CandidateMarket/Improvements | `pages/4_Improvements.py` uses `career_intelligence_presenter` and old snapshot/gap/plan builders | `CandidateMarketService` + existing Now/Next/Watch and Build/Prove/Explore builder | Improvements, dashboard summaries | Old CurrentMarketPosition and candidate-derived market must not be fallback authority | REPLACE |
| Post-hire modes/access | `HiredTransitionService`/repository exist but no UI/runtime caller; `AccessPolicy` does not consume product mode | Existing SEARCH/CAREER/READ_ONLY state and transitions; guarded mutation entry points, historical reads retained | Accepted application actions, Settings, search controls | End request is not confirmed billing/access change; no billing adapter is present | MERGE |
| System/empty/error states | `system_state_presenter` is used for search progress/stopped/quota and disconnected Gmail | Existing presenter consumes authoritative V1 view state | Opportunities/Sources now, other pages at cutover | Remaining inline/legacy evidence-based empty states must not make contradictory claims | MERGE |
| Shadow/backup authority | `hiring_case_shadow_service`, legacy input adapter and semantic shadow tooling are comparison/offline paths, not the current search writer | Offline fixtures/calibration only; no user-visible authority | Tests/scripts; no current production call to authoritative profile service found | Shadow-derived legacy labels cannot be promoted to current HiringCase | DELETE |

The final DELETE row targets shadow/backup **runtime authority**, not blind removal
of useful frozen calibration evidence. Search all callers before deleting files.

## Additional cutover findings (engineering, not additional product questions)

1. **No complete production ProfileInterpreter implementation.**
   `profile_interpreter.py` is a Protocol. `FixtureStructuredInterpreter.interpret`
   implements a different structured request boundary; the real
   `OpenAISemanticEvidenceInterpreter` is explicitly gated shadow semantic support,
   not an implementation of all three profile methods. Reuse validated request/
   response boundaries and the existing transport; do not fabricate an adapter by
   mapping legacy scores into evidence. Preserve paid batching/claims boundaries.
2. **Source laundering risk at Candidate cutover.** Raw confirmed interview answers
   are durable, but legacy generated experience summaries feed the current memory
   payload. A `professional_experience:<id>` reference alone does not prove that
   its summary is an original answer. The cutover must resolve confirmed source
   content and preserve interpretations/checkpoints separately.
3. **Shared job overwrite remains present.** `upsert_raw_job` authorizes changes by
   text length; source ownership is attached afterward. Do not feed shared Market
   from existing mixed-authority `jobs` text merely because a public source link
   also exists. No production contamination inventory was performed in this audit.
4. **No persisted authoritative HiringCase runtime writer/read projection found.**
   Reuse existing scoped analysis/run storage where possible, with explicit schema,
   authority, versions, signatures and surfaced state. Do not rebrand old rows as
   deterministic HiringCases. Preserve applications/notes/history independently.
5. **CV orchestration still has a dual-context risk.** `V1ApplyFlow.prepare` validates
   supplied V1 context, but calls injected `.prepare(candidate_id, job_id)`; the
   current production factory rebuilds legacy context. Wire one authoritative
   context through existing claims/repair orchestration, not two separate truths.

## Preserved WIP assessment: 2bf08cb

Compared by reading commit diff/file contents. No WIP code applied.

| WIP file/idea | V1 compatibility and required adaptation | Action |
|---|---|---|
| `services/job_observation_repository.py` atomic recording/owner scope | Salvage observation/source/canonical transaction and owner-scoped reads. Reconcile with one Job identity and public Market projection; do not blindly install its resolver | MERGE |
| Same file: whole-import global advisory lock | Correctness idea is useful; justify contention and lock ordering with actual PostgreSQL concurrency tests before choosing final granularity | MERGE |
| Same file: public authority chosen by lexical source tuple | Deterministic provenance tie-break, not evidence of superior truth. Preserve attributed conflicts; never treat lexical selection as verified fact | MERGE |
| Same file: private projection as a `jobs` row | Owner-private projection is compatible only with explicit isolation and exclusion from canonical Market. Do not relabel it public merely because a public observation arrives | MERGE |
| `services/job_observation_schema.py` | Additive observation/authority tables and RLS are useful; adapt indexes, stable identity/provenance and idempotency to current schema | MERGE |
| `migrate_job_observations.py` | Retain explicit migration concept; validate isolated PostgreSQL and SQLite, no automatic production backfill | MERGE |
| `services/database.py` insert-only compatibility writer / protected enrichment | Remove length-based overwrite across all equivalent writers; retain candidate analyses/history and avoid deleting current Block 1-13 schema additions | MERGE |
| `services/job_import_service.py` | Route existing importer through reconciled authority rather than separate commits for job/source; retain scheduling/discovery counters | MERGE |
| `services/gmail_job_processor.py` | Owner-scoped observation before marking message processed; retry/idempotency must preserve both owners' data | MERGE |
| `pages/2_Sources.py` | Salvage scoped manual import call site, retaining current OAuth/navigation and system notices | MERGE |
| `services/job_observation.py` tracking normalization | Preserve vacancy query and fragment identity. Current Market identity drops all fragments while WIP retains them; resolve once and test before projecting Market | MERGE |
| `services/job_source_repository.py` transactional connection support | Useful for atomic source association; keep existing ownership checks and source timestamps | MERGE |
| `tests/test_job_observation_isolation.py` | Retain adversarial collision/order/private/public/retry/deletion scenarios; run against reconciled official identity and real isolated PostgreSQL | MERGE |
| `tests/test_source_v2_foundation.py` WIP expectations | Adapt only assertions justified by final provenance contract; preserve existing provider/scheduler coverage | MERGE |
| `docs/job-observation-authority.md` rollout rationale | Keep evidence/history preservation and explicit migration warnings; rewrite claims that imply old resolver is the official V1 identity | MERGE |
| Any second independent Job/Market identity authority | Do not retain competing URL/provider/fuzzy rules after callers switch | DELETE |

The WIP leaves legacy canonical data frozen without inferred authority. This is a
safe migration baseline, not evidence that old content is public or uncontaminated.
Its public resolver's existing-ID path also needs adversarial review: equal
provider ID/URL is not sufficient to ignore conflicting identity metadata.
The whole patch must not be merged as a shortcut.

## Proposed small tested sequence after decision

1. Resolve visibility/sufficiency inside existing HiringCase contracts; add empty,
   partial, unknown, conflicting and positive-evidence regression cases. No label
   substitution from old buckets. Preserve confidence separately.
2. Reconcile observations/identity and source-grounded candidate inputs. Migrate
   additively; retain IDs/history where referenced, no speculative backfill.
3. Connect official profile interpreter/snapshots and scoped HiringCase storage to
   existing cooperative preparation/batch/claim runner. Switch selector, activation,
   categories and job-analysis view together. Persist unavailable versus ineligible.
4. Thread the same versions/evidence into CV generation/edit/export and explicit
   apply confirmation. Switch applications to sequenced rounds and InterviewBrief.
5. Project eligible public observations into Market snapshots, then use
   CandidateMarket for Improvements; no candidate-derived global fallback.
6. Wire mode actions and server mutation guards, leaving read-only history usable.
   End subscription remains an intent; missing research/billing is unavailable.
7. Replace remaining notices. Search remaining production callers, remove/demote
   old authority only after tests prove replacement. Commit only green slices.

## Integration and release proof required

- Durable source answer -> reload -> source evidence -> CandidateProfile with the
  same source refs; draft excluded, corrections/version changes invalidate caches.
- Public ingestion -> canonical Job -> JobHardFacts/JobProfile; private imports
  cannot rewrite or contribute private payloads to global Market.
- Official snapshots -> Hard Filter -> HiringCase -> surfaced/category UI;
  UNKNOWN never implies hard rejection and insufficient evidence never invents
  competitiveness. Preserve max-10 eligible batching, stop, claims and races.
- Same profiles/HiringCase -> CV -> edited CV validation -> export validation;
  external URL open leaves stage unchanged, confirmation changes Applied once.
- Application/round/company scope -> brief; earlier feedback reaches later round
  without becoming candidate fact. No Response and Accepted remain explicit.
- Global Market -> candidate-specific plan; improvements and modes never mutate
  source evidence. Accepted alone leaves mode unchanged. End request is not billing.

PostgreSQL validation must use an explicitly isolated disposable database. Do not
reuse `.env` DATABASE_URL: earlier project context identifies it as production.
No target was connected/validated in this audit. Use synthetic historical/fresh
users and scoped fixtures, apply additive migrations twice, test snapshot history,
draft/resume/finalize, claims/concurrency, rounds, state events and RLS/transaction
rollback using a real PostgreSQL server. SQLite/fake SQL results are not substitutes.

Browser gate: isolated local Streamlit + test database, fresh-account golden path,
refresh mid-interview, page navigation, multiple tabs/users and mode mutation guards.
Offline doubles can prove UI wiring first; real voice/AI/provider E2E needs explicit
credentials/budget and must be reported separately. No real external application
submission or billing action should be fabricated to satisfy a test.

Release remains blocked until full/integration/PostgreSQL/browser gates pass,
Critical/High logic/data-integrity findings are resolved, runtime legacy authority
is removed, and worktree/diff checks are clean. No merge to main is authorized.

## Initial audit execution record

- Read-only repository and preserved-WIP inspection; production files unchanged.
- Pure in-memory empty-requirement reproduction returned a visible strong category.
- Existing HiringCase focused suite: **84 passed** (authoritative service, engine
  and evidence constraints). Current coverage does not detect the empty-input
  reproduction above; passing tests are not proof that the gap is absent.
- Initial audit stops at the visibility policy decision above. No implementation,
  schema execution, provider call, commit, push or WIP merge was performed.

## Approved sufficiency cutover

The resolved policy is implemented in the HiringCase engine, schema v2. Zero
grounded CORE/IMPORTANT evaluations produce NOT_SURFACED with
insufficient_evidence, preserving requirements and questions for enrichment.
Grounded positive support is required for any visible recommendation; proven
hard incompatibilities remain INELIGIBLE regardless of sufficiency.

Frozen historical calibration judgments remain unchanged. Three of the forty
historical cases now abstain rather than surface; replay reports retain those
differences instead of rewriting the historical evidence to manufacture agreement.

The next source-boundary integration reads confirmed persisted onboarding answers
into the official profile service. Drafts and generated legacy Candidate summaries
are not accepted as source evidence on this path. Narrative answers cannot certify
complete finite-fact coverage or authoritative absence. This entry point is not
yet wired into every production caller; the runtime cutover and release gates above
remain outstanding.
