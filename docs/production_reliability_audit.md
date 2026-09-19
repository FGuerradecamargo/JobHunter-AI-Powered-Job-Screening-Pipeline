# Production Reliability Audit

Date: 2026-09-19. Frozen Beta scope; global readiness remains **70%**.

Current status after the separately authorized local TRUST remediation: **CONDITIONALLY READY FOR LIVE CHECKS**. T1 and T2 are remediated offline; see section 17. Sections 1-16 retain the original audit evidence and historical verdict, not a claim that the subsequent working tree is code-unchanged.

## 1. Scope and Checkpoint

- Branch: `feature/postgres-migration`.
- Exact audited commit: `de0e724bfc997b6e12386030ba0e9af7ac048326` (`docs: record real voice onboarding validation`).
- Initial working tree: clean. Only this report was added.
- No production code, configuration, schema or tests changed. No commit or push.
- No production connection, credential inspection, external AI, email, OAuth or provider request was made.
- This is static inspection plus network-blocked offline regression, not a penetration test or certification of deployed configuration.
- Concept/pointer graphs, new telemetry systems and architectural redesign are out of scope.

## 2. Evidence Inspected

Entrypoints and UI: `streamlit_app.py`, `app.py`, `pages/0_Login.py`, `pages/1_Opportunities.py`, `pages/2_Sources.py`, `pages/3_Profile.py`, navigation declarations, `.streamlit/config.toml`, and `docs/release_oauth_search_hardening.md`.

Authentication: session authentication/store/bootstrap, active-user session/context/runtime, access policy, admin access/reauthentication, Google identity/account services, OAuth state, token encryption, and their regression tests.

Data boundaries: `services/database.py`, source/run/global schema helpers, candidate onboarding/history/objective repositories, job search/source repositories, application preparation/lifecycle/outcome and interview paths. Reviewed caller-supplied candidate IDs as well as SQL predicates; repository methods alone are not authentication boundaries.

Generation and privacy: candidate job analysis, OpenAI client, preparation factory/service/UI/diagnostics, company interview/reflection, voice UI/transcription, profile prompt builder, security audit repository and relevant exception sinks.

Local scans: tracked-file names and credential-shaped literals; environment getters; runtime synthetic markers; table creation and RLS/revoke statements; test transports and isolation fixtures. Scans were bounded to the current repository, not complete Git history or deployment logs. No secret values were displayed.

## 3. Canonical Deployment

The canonical shell is **`streamlit_app.py`**, which chooses authenticated navigation before `navigation.run()`. `app.py` is the Dashboard page, not an equivalent security/navigation shell. Files under `pages/` are page implementations. Do not deploy `app.py` or a page as the application entrypoint.

Authenticated navigation uses the active user's candidate, limits incomplete profiles to Profile, and registers Sources explicitly at `Sources`. The shell also checks an admin target against the reauthentication grant before running a page (`streamlit_app.py`, authenticated branch starting at line 319). Page-local active-user resolution does not independently verify that grant. Thus the canonical shell is part of the security boundary, not just a visual wrapper.

Run from the repository root so `.streamlit/config.toml` applies. Required setting: `[runner] fastReruns = false`. Opportunities refuses new searches if the effective setting is true. The committed hostname-independent configuration does not prove the selected Cloud entrypoint, branch or revision.

Gmail callback requirements:

```text
GOOGLE_OAUTH_REDIRECT_URI=https://<actual-production-host>/Sources
Google sign-in redirect: https://<actual-production-host>/oauth2callback
```

Match the registered scheme, host, route case and trailing slash exactly. These are different OAuth flows. Gmail success clears query parameters and explicitly calls `st.switch_page("pages/2_Sources.py")` (`pages/2_Sources.py:259`). Invalid state/error paths do not use success navigation. Callback destinations are not accepted from user input. PKCE and initiating actor binding remain in place.

A wrong configured Gmail hostname moves the browser to another deploy **before** callback handling; the local switch cannot correct that. Production host, Streamlit Google auth configuration, authorized Google redirects and deployed revision remain live configuration checks. No deployed secret was guessed.

## 4. Authentication and Isolation

### Proven local boundaries

- Server session lookup, hashed token, absolute seven-day expiry and sliding 60-minute idle expiry are in `services/session_auth.py`. Exactly 60 minutes is valid; more than 60 is expired. Valid activity does not extend absolute expiry. Expired rows are revoked and local authentication state cleared.
- `require_authenticated_user()` precedes protected page data access. URL parameters are not used to select arbitrary candidates in the reviewed journey.
- Active-user state is bound to the authenticated owner. A normal user's foreign active ID is rejected/reset. Admin viewing-as in the canonical shell requires password reauthentication of the same authenticated admin and an explicit target grant.
- Google identity resolution uses provider plus subject. An existing email without a linked subject requires account-password confirmation rather than automatic linking. Streamlit's upstream OIDC verification/configuration is outside the local identity resolver.
- Opportunities derives `candidate_id` from `active_user.candidate_id`. `JobSearchRepository.list_jobs_to_analyze_for_candidate` filters sources to global provenance or users owning that candidate, and candidate-job joins include candidate ID. Personal Gmail source ownership is not treated as global provenance.
- Dashboard/tracking uses the resolved candidate. Preparation services validate candidate/job consistency; cached CV keys and returned IDs are checked. Interview/outcome SQL is candidate/job scoped. Candidate history/onboarding/objective updates constrain both record and candidate where applicable.
- Voice draft scope hashes actor, active user and candidate. `bind_scope` clears prior voice state when scope changes. Logout/expiry explicitly clears voice/onboarding/admin/search state. Raw audio is held in session memory, not written by the reviewed transcription/interview persistence path.
- Confirmed company answers are stored as source statements. Reflection is a separate untrusted draft with quote checks and is not automatically persisted as evidence.

### Limits, not claims of exploitability

Backend repositories accept IDs; they do **not** all authenticate an actor. For example, onboarding update constrains `id AND candidate_id`, but a caller possessing both IDs is not independently authorized by that method. Protection relies on the canonical authenticated caller chain and inaccessible backend credentials. No HTTP endpoint allowing a normal user to invoke these repositories directly was found; direct PostgREST access is separately unverified.

Admin reauthentication is enforced in the shell, not every repository/context resolver. Standalone deployment of a page is not approved by this audit. No demonstrated normal-user cross-account read/write path was found in the reviewed canonical flow.

Logout is not a blanket deletion of every Streamlit key. Candidate/job keyed preparation and tracking state can remain in memory, but reviewed loaders check the current candidate. The no-cookie path removes `current_user` without performing the full logout cleanup; subsequent voice rendering rebinds scope. Immediate raw-audio cleanup on unexpected cookie loss and real two-account browser transitions remain manual verification items, not a proven cross-account disclosure.

**Confirmed integrity defect:** guided-experience narrative edits are saved and acknowledged, but omitted from subsequent profile-generation input. See T1.

## 5. PostgreSQL / RLS Inventory

All listed relations are used through the Python backend. No reviewed browser path needs direct PostgREST access to these tables. Application tenant filters and RLS solve different problems: RLS without tenant policies does not constrain a privileged backend role.

| Repository-declared posture | Tables |
| --- | --- |
| RLS enabled plus explicit table revokes from PUBLIC and existing anon/authenticated roles | `candidate_profile_snapshots`, `job_profile_snapshots`, `company_interview_answers` |
| RLS enabled; no explicit table revokes found in creation helper | `candidate_interview_details`, `candidate_interview_feedback`, `candidate_preparation_generation_claims`, `companies`, `candidate_monitored_companies`, `company_job_sources`, `source_ingestion_state`, `source_ingestion_runs` |
| No RLS enablement/revokes found in these creation paths | `candidates`, `users`, `user_identities`, `user_sessions`, `auth_login_failures`, `account_action_requests`, `account_action_tokens`, `security_audit_events`, `candidate_onboarding`, `candidate_work_experiences`, `candidate_career_updates`, `candidate_career_objectives`, `candidate_objective_profiles`, `candidate_career_development`, `candidate_career_memory`, `candidate_career_memory_events`, `jobs`, `job_sources`, `job_discovery_signals`, `job_profiles`, `candidate_job_analyses`, `candidate_job_analysis_runs`, `candidate_application_outcomes`, `gmail_connections`, `gmail_messages`, `oauth_authorization_states` |

Inventory: **37 distinct application tables**. Sources: `services/database.py`, `services/session_store.py`, `services/source_run_schema.py`, `services/job_profile_manager.py`. Temporary SQLite migration replacement tables are not additional production tables.

`database.py:634-657` explicitly allowlists the RLS helper; snapshot revokes are near line 830, company-answer revokes near line 2686. There are no repository-created tenant policies in the scanned Python schema paths. Enabling RLS with no policy denies ordinary direct row access, but does not remove existing permissive policies, revoke all other ACLs, or constrain table owners/BYPASSRLS roles. The helper does not FORCE RLS.

Newer snapshots/company answers carry explicit security posture. `user_sessions` and dynamically created `job_profiles` are examples outside that helper. A previous manual hardening pass is not reproducible from these creation paths alone.

**Not established:** whether any of the third-group tables are exposed in production. Live RLS flags, grants/default grants, policies, exposed schemas, RPCs/views and role memberships may differ. Do not label this a confirmed public data leak. The database gate remains unverified until the read-only catalog review below. Do not enable RLS blindly without checking the backend role and migration behavior.

## 6. Secrets and Privacy

- `.gitignore` covers `.env`, `.streamlit/secrets.toml`, credential/token files and database files. Current tracked-file inspection found none of those credential files or private-key files.
- A current-tree scan for common OpenAI/Google key, private-key and credential-bearing PostgreSQL URL shapes returned no matches. This is not an exhaustive secret-history audit.
- Session cookie key resolves normalized environment then Streamlit secrets and fails closed. Voice configuration supports environment/secrets fallback.
- Environment-only consumers remain: `DATABASE_URL`, OpenAI API key/model, Gmail client ID/secret/redirect, `TOKEN_ENCRYPTION_KEY`, and email API/from settings. Correct top-level Streamlit secret-to-environment loading must be verified on the actual deployment; no conclusion that configured Cloud secrets are currently broken follows from these getters alone.
- Missing `DATABASE_URL` selects SQLite. The approved production deployment must explicitly prove PostgreSQL is selected; a missing variable must not be mistaken for a healthy production database.
- Gmail tokens use encryption, not plaintext storage by the reviewed repository. Session tokens are server-hashed. Token encryption key rotation/recovery and actual deployment secret handling were not exercised.
- Unsanitized exception sinks remain in analysis and Gmail handling (T2). No actual secret leak was observed; the defect is that arbitrary upstream exception text is accepted into persistent/UI/log sinks.

## 7. Synthetic Data

Runtime service/page scans found no `pg-test` / `Postgres Test Co` seeding or fallback synthetic candidates/jobs in the reviewed production paths. New-user bootstrap creates an empty candidate rather than a template career history. Fixtures/scripts containing examples are not evidence of a reachable automatic production seed.

`tests/conftest.py` overrides `DATABASE_URL` before importing the database module, redirects SQLite to temporary paths, and blocks the PostgreSQL pool per test. The suite did not use the application database. Two PostgreSQL-specific tests were skipped; they must never be enabled against production because their bodies create schema.

Existing contamination cannot be excluded from repository inspection. A previously inserted job can still be served if it has legitimate-looking source/candidate links; absence of a current seeder does not remove old rows. Later read-only counts are provided below; matching names alone do not prove synthetic origin.

## 8. Empty / Error / Recovery States

| Journey/state | Assessment |
| --- | --- |
| Login/expired session | Auth gate stops access; idle/absolute expiry and Google reauthentication guard covered offline. |
| New/incomplete profile | Shell routes to Profile; missing candidate fails safely rather than selecting a sample candidate. |
| Empty catalog/no worthwhile opportunities | Search records completion without fabricated results; accepted-result target differs from examined-job count. |
| Job Profile/Hiring Case/preparation | Candidate/job contracts and Truth Guard reject invalid content; safe tailored-CV diagnostic codes and bounded repair are present. |
| Tracking/outcomes/interview | Candidate/job-scoped actions and empty/edit flows covered by full regression; not a live browser usability certification. |
| Partial/stopped search | Results stay persisted; next unit is suppressed after scoped cancellation is observed. |
| Failed transcription | Explicit retry or typed replacement; other answers retained. No automatic transcription retry. |
| Failed reflection | Source answers can continue, but the production default provider is unavailable and retry cannot change that (F3). |
| Gmail disconnected/invalid state | Connection management and fail-closed callback paths exist. Missing Gmail configuration can prevent Sources rendering at all (F2). |
| Provider/DB failure | Some feature actions map safe failures; bootstrap/page repository reads are not universally wrapped. Core DB outage is not equivalent to an empty dataset and can stop the page. No destructive fallback observed. |
| Malformed generated/job data | Schema/contract tests reject malformed artifacts. Search raw exceptions still need sanitization (T2). |

The audit did not navigate the live application or initiate any product action that could charge, send mail or modify production.

## 9. Cost, Retry and Cancellation

Opportunity search is incremental across reruns. Scope includes actor, active user, candidate, profile signature and scan ID. First unit activates existing accepted analyses; later units select at most one job. Stop is observed between complete analysis/persistence units. It cannot interrupt an in-flight unit, which may include enrichment, job-profile generation and candidate analysis. Accepted results are preserved and later fresh runs are independent.

Search screens an existing shared catalog; it does not launch provider ingestion on page render. The 5/10/15 target caps accepted activations, not all analyzed/rejected jobs. `AIUsageBudget.unlimited()` is used for this search: a large unsuitable catalog can therefore cost substantially more than the requested result count. The loop terminates by target/exhaustion/failure/stop; no unbounded retry loop was identified, but this is **not a fixed monetary cap**.

Tailored CV: explicit action, same-context persistent lease, session cache, initial generation plus at most one semantic repair, claim release in `finally`. Completed CV reuse remains session-local; another session can generate after release. These are not promises of global exactly-once billing.

Voice: explicit authorization before transmission, bounded audio, no raw-audio file write, zero SDK retries and 30-second timeout (`services/ai/voice_transcription.py:60`). Interview transcription is deferred to the explicit processing step. Reflection requires authorization and does not retry automatically.

General `OpenAIClient` does not set retry/timeout overrides. The installed SDK defaults inspected offline are two automatic retries and 600 seconds read timeout, unlike voice/shadow. Therefore one logical generation can entail more than one HTTP attempt. This can substantially delay observing Stop and recovery (F1). Production SDK version still needs checking. No provider was instantiated for this defaults inspection.

## 10. Observability

Positive controls: security audit events have actor/active IDs, outcomes and restricted scalar metadata; tailored-CV diagnostics expose stage/issue codes without full generated CVs; source-run metadata records status/counts; voice results carry sanitized request IDs/model/duration. Source answers and derived reflection have separate persistence treatment.

The audit metadata filter is key-based, not a guarantee that arbitrary string values are safe. Current event callsites must continue passing controlled metadata. Raw exception logging is the material remaining privacy gap, not a reason to build a telemetry platform. Transport storage/retention settings, actual deployed log levels and provider retention are not certified by offline tests.

## 11. Findings

| ID | Category | Evidence | Risk | Minimum fix | Gate impact |
| --- | --- | --- | --- | --- | --- |
| T1 | TRUST | `pages/3_Profile.py:471-538` saves edited narratives; `services/candidate_onboarding_repository.py:235-275` updates only legacy narrative fields; `services/ai/candidate_profile_prompt_builder.py:22-24` blanks those fields when confirmed answers exist | User sees "Experience updated" while generation still uses superseded source answers; corrections can silently be ignored | Make guided-source corrections authoritative and explicitly confirmed, or stop offering misleading narrative edits for guided records until source editing is supported. Preserve source/derived separation; add save-to-prompt regression | Must resolve before Beta |
| T2 | TRUST | `services/candidate_job_analysis_service.py:1603,1612,2124,2133` persists/returns `str(error)`; `pages/1_Opportunities.py:867` renders errors; `pages/2_Sources.py:244,491` logs exception chains | Provider exceptions can contain sensitive responses or credential-bearing URLs; current code has no allowlist boundary at these sinks | Replace raw exception payloads with controlled stage/code and sanitized request ID; avoid exception-chain logging for upstream errors; add adversarial fake-secret/content tests | Must resolve before Beta; no observed real disclosure claimed |
| F1 | FRICTION | `services/ai/openai_client.py:28-42` leaves timeout/retries to SDK; installed defaults 600-second read timeout/two retries; search observes cancellation after a complete unit | Long apparent hangs, delayed Stop, additional HTTP attempts not apparent from the one-repair limit | Set explicit finite product-appropriate transport timeout/retry policy; retain cooperative stop and document accepted vs examined limit | Resolve if recurring; verify bounded failure/Stop before gate closure |
| F2 | FRICTION | `pages/2_Sources.py` constructs Gmail services before connection controls; `services/gmail_oauth_service.py` rejects missing environment configuration at construction | Missing optional Gmail config can take down Sources rather than show unavailable connection controls | Catch configuration-only failure at feature initialization and disable Gmail actions with a safe message | Conditional: verify configured deployment; fix before offering unconfigured feature |
| F3 | FRICTION | `components/profile_onboarding.py:563,741-742` defaults reflection provider to None; `components/company_interview.py:16,124-130` selects unavailable provider and offers Retry | Normal production reflection attempt always reaches unavailable state; retry cannot recover configuration, although source-only continuation works | Make unavailable mode deliberate: skip futile retry and clearly continue source review; do not add a new AI provider as part of this audit | Nonblocking source-only path; remove misleading recovery before promising reflection |

Totals: **0 BLOCKER, 2 TRUST, 3 FRICTION**. No cosmetic/new-idea backlog added. Unverified live permissions/configuration are closure requirements, not invented confirmed vulnerabilities.

## 12. Test Evidence

Focused selection: session/auth security, admin access, active-user state, candidate onboarding/history/objective ownership, Gmail navigation/state/token security, new-user bootstrap, opportunity cancellation, preparation cost guard, voice service/UI, company interview/reflection, security audit repository.

Result: **251 passed in 19.60s**.

Full suite: **1746 passed, 2 skipped in 73.53s**. No failures or material warning summary. Skips are the two PostgreSQL schema checks in `tests/test_candidate_job_analysis_run_schema.py`, explicitly because PostgreSQL is not configured in tests. SQLite/fake-PG tests do not certify real PostgreSQL migrations, grants or concurrency.

Execution used the existing local Python environment, `PYTHONDONTWRITEBYTECODE=1`, empty `DATABASE_URL`, test temporary database fixtures, and an additional process-level denial of `socket.socket.connect`, `connect_ex` and `getaddrinfo`. Reviewed integration test paths use fake transports/monkeypatches. No network-denial failure occurred. The PostgreSQL pool fixture is forbidden; no live database test was enabled.

Additional pure in-memory synthetic reproduction for T1 (no DB/client): edited story forwarded = false; edited day-to-day forwarded = false; original confirmed answer forwarded = true. No private candidate text was used or printed.

`git diff --check`: passed after report creation. Working tree: only this untracked report; production code remains unchanged.

## 13. Remaining Offline Limits

Not checked: actual Cloud entrypoint/branch/revision, effective secrets/config, Google redirect registrations, live user/session transitions, PostgreSQL ACL/RLS/default privileges/roles/views/RPC exposure, existing contamination, database backup/restore state, production provider latency and upstream retention. Historical validation notes are not a substitute for inspecting current deployment configuration. No global readiness increase is justified by passing tests alone.

## 14. Minimal Remediation Order

1. Approve a narrow implementation slice for T1 and T2, each with a failing offline reproduction followed by focused/full regression. No AI calls are needed.
2. Decide whether reflection is intentionally source-only for frozen Beta; remove futile retry if so. Verify Gmail configuration and evaluate explicit general-client timeout/retry bounds without broad refactoring.
3. Confirm the canonical Cloud entrypoint/revision and required configuration, without displaying secret values or triggering OAuth/email/AI.
4. Run the catalog-only PostgreSQL checks below under separate authorization. If unexpected direct access is found, treat that concrete result as a release blocker and design the minimum grants/RLS fix against the actual backend role.
5. Perform later controlled two-account browser checks and empty/error/cancel flows using fakes or separately approved live actions. Close the gate only after TRUST fixes and configuration/access evidence are complete.

## 15. Exact Later Read-Only Checks

**Not executed.** Obtain separate authorization for the production connection. Use a direct database client, not application bootstrap (bootstrap can create/alter schema). Never print the connection string. Start and confirm a read-only transaction before catalog queries; abort if read-only is not on.

```sql
BEGIN TRANSACTION READ ONLY;
SHOW transaction_read_only;
SELECT current_user AS backend_role,
       current_schema() AS application_schema;

-- Public application tables and actual RLS state.
SELECT n.nspname AS schema_name, c.relname AS table_name,
       pg_get_userbyid(c.relowner) AS owner_role,
       c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY c.relname;

-- Effective table privileges include inherited grants. No row data returned.
SELECT r.rolname, c.relname AS table_name,
       has_table_privilege(r.oid, c.oid, 'SELECT') AS can_select,
       has_table_privilege(r.oid, c.oid, 'INSERT') AS can_insert,
       has_table_privilege(r.oid, c.oid, 'UPDATE') AS can_update,
       has_table_privilege(r.oid, c.oid, 'DELETE') AS can_delete,
       has_table_privilege(r.oid, c.oid, 'TRUNCATE') AS can_truncate
FROM pg_roles r CROSS JOIN pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE r.rolname IN ('anon', 'authenticated', current_user)
  AND n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY r.rolname, c.relname;

-- Policy metadata only. Inspect expressions privately in the dashboard if needed.
SELECT schemaname, tablename, policyname, roles, cmd, permissive,
       qual IS NOT NULL AS has_using_expression,
       with_check IS NOT NULL AS has_check_expression
FROM pg_policies WHERE schemaname = 'public'
ORDER BY tablename, policyname;

SELECT rolname, rolsuper, rolbypassrls
FROM pg_roles
WHERE rolname IN ('anon', 'authenticated', 'service_role', current_user);

SELECT parent.rolname AS granted_role, member.rolname AS member_role
FROM pg_auth_members m
JOIN pg_roles parent ON parent.oid = m.roleid
JOIN pg_roles member ON member.oid = m.member
WHERE member.rolname IN ('anon', 'authenticated', current_user);

SELECT pg_get_userbyid(d.defaclrole) AS owner_role,
       COALESCE(n.nspname, '<all schemas>') AS schema_name,
       d.defaclobjtype, d.defaclacl
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
WHERE n.nspname = 'public' OR d.defaclnamespace = 0;

-- Views and callable functions can expose data independently of table ACLs.
SELECT r.rolname, c.relname AS view_name,
       has_table_privilege(r.oid, c.oid, 'SELECT') AS can_select,
       c.reloptions
FROM pg_roles r CROSS JOIN pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE r.rolname IN ('anon', 'authenticated')
  AND n.nspname = 'public' AND c.relkind IN ('v', 'm');

SELECT r.rolname, p.oid::regprocedure::text AS function_name,
       p.prosecdef AS security_definer,
       has_function_privilege(r.oid, p.oid, 'EXECUTE') AS can_execute
FROM pg_roles r CROSS JOIN pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE r.rolname IN ('anon', 'authenticated') AND n.nspname = 'public';

ROLLBACK;
```

Compare returned tables against all 37 inventory entries; investigate missing and extra tables. If a non-public application schema or additional exposed schema exists, repeat the same catalog filters for that known schema. Check Supabase API exposed schemas separately in the dashboard. Do not invoke functions or fetch private rows to test access. RLS policies, effective role privileges and backend ownership must be evaluated together; no policy does not imply owner access is denied.

Optional later contamination/session-shape counts, also read-only and separately authorized:

```sql
BEGIN TRANSACTION READ ONLY;
SHOW transaction_read_only;
SELECT count(*) AS suspect_job_count
FROM public.jobs
WHERE lower(trim(company)) = 'postgres test co'
  AND lower(trim(title)) = 'fraud operations analyst';

SELECT count(*) AS sessions_without_activity
FROM public.user_sessions
WHERE last_activity_at IS NULL OR trim(last_activity_at) = '';
ROLLBACK;
```

First verify the table/column inventory; do not repair schema to make a diagnostic run. A nonzero suspect count requires ID-bound provenance/ownership investigation, not deletion. These counts intentionally omit emails, tokens, CVs, notes and narratives.

Deployment/browser checklist for later:

1. Cloud settings: entrypoint `streamlit_app.py`, intended branch/revision, repository-root configuration and effective `fastReruns=false`; confirm PostgreSQL selection and required secret presence as booleans only.
2. Compare Gmail `/Sources` and Google sign-in `/oauth2callback` on the same approved production host against their separate registered redirects. Configuration review needs no OAuth request.
3. With approved test accounts, verify normal users cannot select another active user; admin target data appears only after reauthentication; logout/expiry clears voice and prevents stale prepared/profile content crossing accounts. Include two tabs and unexpected cookie removal.
4. Verify empty profile/catalog, invalid callback, typed fallback after transcription failure, source-only reflection continuation, CV rejection, and Stop preserving accepted results. Any live AI/OAuth/email action requires separate approval; use fakes otherwise.
5. After any separately approved contamination remediation, verify legitimate opportunities/category counts and another user's visibility remain unchanged. This audit authorizes no cleanup.

## 16. Original Audit Gate Verdict

**NOT CLOSED.** Two confirmed TRUST issues remain, plus unverified production deployment/database boundaries. Zero demonstrated BLOCKER findings does not mean the gate is closed. Global Beta readiness remains **70%**; audit task is complete. Next action: approve the narrowly scoped offline T1/T2 remediation, without live calls, production data access, commit or push.

## 17. Authorized TRUST Remediation (Local, Uncommitted)

### TRUST-01 / T1: Remediated Offline

Root cause: the experience editor updated `career_story` and `day_to_day_narrative`, while the generation prompt deliberately excluded those projections whenever confirmed interview answers existed. Saving a correction therefore did not replace the original authoritative input.

Implementation:

- Guided narrative changes require an explicit UI confirmation and `confirmed_source_edit=True` at the repository boundary. Merely editing widgets or passing an unconfirmed draft cannot alter the source.
- The owner-scoped update appends a `USER_CONFIRMED_EDIT` source record to the existing `company_interview_answers` table in the same transaction. No table/column migration is needed. The record contains the user-confirmed replacement account, source/version labels, revision ID and confirmation timestamp, not generated interpretation.
- Original question answers and earlier corrections are preserved. `list_company_answers(..., include_history=True)` retrieves that history under the same candidate/experience ownership constraint. The normal generation loader returns only the latest confirmed correction when present, so stale answers are not preferred or mixed back into the current input.
- Revision allocation follows the experience UPDATE lock. Subsequent changed confirmations append another revision rather than overwrite the original interview. Without explicit source confirmation, metadata-only edits leave the interview answers untouched. Repeated confirmation of unchanged, already confirmed text does not append duplicate revisions.
- The profile prompt identifies the replacement as user-confirmed source, not AI interpretation. The fixed question bank and generation architecture are unchanged. Career Memory continues consuming the resulting Candidate Profile through its existing refresh path; this fix does not promote deterministic inference or trigger automatic AI work on save.

Evidence: `pages/3_Profile.py`, `services/candidate_onboarding_repository.py`, `services/ai/candidate_profile_prompt_builder.py`. Seven tests in `tests/test_guided_experience_corrections.py` cover confirmed input, draft rejection, newest correction precedence, preserved history, foreign-candidate rejection, metadata-only behavior, confirmation of previously saved legacy text, and the actual generation service's request using a fake client. Existing repository security tests were adapted to the new pre-update read while retaining UPDATE owner assertions.

Existing old edits are not retroactively guessed or converted into source. A guided narrative previously saved before this fix is not automatically promoted: the user must explicitly confirm and save the replacement account. They need not artificially alter the already saved text to confirm it. Original interview history remains preserved after that action.

### TRUST-02 / T2: Remediated Offline

Root cause: exception interpolation/stringification in job-analysis failure records/results, Gmail processing/background results, provider callback/profile logging, and a Career Memory interpretation result accepted arbitrary upstream text. The OAuth error-description query string was also echoed to the UI.

Implementation:

- `services/provider_failure.py` supplies one allowlisted diagnostic boundary. Returned/persisted codes are `provider_timeout`, `provider_error`, `provider_rate_limited` or `operation_failed`; logs use a fixed operation stage and controlled error-kind metadata, never exception text, response bodies or traceback chains.
- Real OpenAI generation and Gmail OAuth/sync entrypoints translate known SDK/transport exceptions into sanitized exceptions with suppressed chaining. Programmer exceptions such as TypeError are not caught by this transport boundary; a regression proves they propagate. Existing outer UI/service recovery behavior is retained rather than adding silent broad catches.
- OpenAI rate-limit semantics remain observable via `ProviderRateLimit`; candidate analysis still sets its quota-exhausted flag and stops the batch. Retry counts/timeouts were not changed in this TRUST slice.
- Existing thread-local transport log protection is reused/extended to known Google/OAuth/urllib transport loggers. General generation now uses it as well. No prompts, raw response payloads or credentials are logged by the new diagnostic helper; request IDs are not copied from arbitrary exception attributes.
- Job-analysis preparation/batch/persistence errors and Gmail processing errors now pass safe codes to persistence. Background Gmail returns/logs safe codes. Opportunities no longer renders arbitrary error objects. Gmail callback/sync and Profile generation log safe stages. OAuth error descriptions are not echoed.
- Enrichment no longer prints URLs or exception bodies. Career Memory returns a safe interpretation error code. Tailored-CV parse failure objects use fixed messages even if a fake/untrusted client raises the parser exception class with hostile text.
- Voice transcription and semantic shadow already returned bounded failure codes and used private transport logs; their existing offline regression paths remain green. Transactional email already translates transport errors into controlled internal messages without chaining; no email feature changes were needed. Existing database-only diagnostics were not indiscriminately disabled.

Evidence: 15 tests in `tests/test_provider_failure_privacy.py` exercise hostile fake keys, Authorization headers, CV/email text, JSON payloads and traceback-like strings. Assertions cover persistence-bound fields, returned failure objects, real callback UI handling, logs/stdout, formatted exception chains, timeout classification, and rate-limit/programmer-error behavior. Analysis trace and Career Memory tests now expect safe codes rather than raw exception messages; Gmail callback fixture includes the real safe logger helper.

### Final Offline Verification

- Focused TRUST plus adjusted ownership/memory tests: **29 passed in 2.83s**.
- Relevant security/auth/isolation/onboarding/profile/provider regression: **807 passed, 2 skipped in 45.75s**.
- Full offline suite: **1768 passed, 2 skipped in 96.71s**.
- Added coverage: 22 new test cases across two new files; four existing test files updated.
- The initial extended run identified two outdated SQL cursor doubles and one raw-error expectation. Those were corrected and the complete selection rerun successfully. No remaining failures.
- All runs used the existing local Python environment, temporary test databases, empty `DATABASE_URL`, and socket connect/DNS denial. No external request or production database operation occurred. The two skipped real-PostgreSQL schema tests remain disabled.
- `git diff --check`: passed; only the existing LF/CRLF conversion warnings. New files were also checked for whitespace errors.
- Branch remains `feature/postgres-migration`; no commit/push. Only the following 23 files differ from the audited checkpoint (this pre-existing untracked report included).

### Exact Changed Files

```text
docs/production_reliability_audit.md
pages/1_Opportunities.py
pages/2_Sources.py
pages/3_Profile.py
services/ai/candidate_profile_prompt_builder.py
services/ai/openai_client.py
services/ai/openai_semantic_interpreter.py
services/candidate_job_analysis_service.py
services/candidate_onboarding_repository.py
services/career_memory_manager.py
services/gmail_background_sync_service.py
services/gmail_job_processor.py
services/gmail_oauth_service.py
services/gmail_sync_service.py
services/job_details_fetcher.py
services/provider_failure.py
services/tailored_cv_generation_service.py
tests/test_candidate_job_analysis_trace_wiring.py
tests/test_candidate_onboarding_repository_security.py
tests/test_career_memory_manager_interpretation.py
tests/test_gmail_oauth_navigation.py
tests/test_guided_experience_corrections.py
tests/test_provider_failure_privacy.py
```

### Updated Gate and Next Approval

**CONDITIONALLY READY FOR LIVE CHECKS**, not CLOSED. Both original TRUST findings are remediated in the local working tree with offline evidence. The three original FRICTION findings and all deployment/RLS unknowns retain their original status; this slice did not implement them. Global readiness stays **70%**.

Next action: separately authorize the production read-only verification in section 15. Confirm the Cloud entrypoint/revision and effective required configuration without printing secrets, then use a direct PostgreSQL client with `BEGIN TRANSACTION READ ONLY` and verify `transaction_read_only` before the catalog/ACL/RLS checks. Do not import application bootstrap, run migrations, enable the skipped schema tests, or call AI/OAuth/email/providers. Review actual table grants, policies, exposed schemas and backend role before deciding whether any production security change is needed. No production mutation is authorized by this report.
