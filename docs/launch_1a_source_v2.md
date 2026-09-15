# Launch 1A: Source V2 foundation

## Audit: before

- JobSource was an ABC exposing search(keywords, location, page, results_per_page)
  returning list[Job]. Adzuna and Jooble converted payloads inside search.
- DailyIngestionService constructed both providers directly. Their country,
  location and query counts were hardcoded. A constructor failure aborted the day.
- Query exceptions were printed with repr(error), potentially exposing credentials
  embedded in URLs. Queries_run counted only successful imports.
- Jobs were deduplicated by their ID only (adzuna:<id>, jooble:<id>, manual URL hash,
  or email parser ID). Candidate discovery separately used title/company/location
  equivalence. That candidate-analysis behavior is unchanged.
- upsert_raw_job retained existing content unless new raw_text was longer.
- job_sources could represent multiple sources only after the standalone
  PostgreSQL-only migration. Base initialization still created a personal-only table.
- discovered_at and last_seen_at represented first and latest source observations.
  Global imports unarchived jobs; archive SQL used PostgreSQL-only BOOL_AND and %s.
- Gmail and manual imports supplied user_id, but global/discovery readers did not
  enforce provenance scope. Provenance listing also returned all owners.
- Candidate analysis lives in candidate_job_analyses and remains candidate-scoped.

## After

ProviderConfig -> JobSourceProvider.search -> JobObservation normalization
-> conservative canonical ID resolution -> raw job upsert
-> per-source provenance/freshness -> global or owner-scoped discovery.

### Provider configuration

services/job_sources/provider.py defines a structural Protocol using the existing
search signature and source_type. ProviderConfig contains source_type, a lazy
factory, location, results_per_query, enabled and query_plan. Factories resolve
credentials at runtime; the registry is not persisted.

The default registry preserves Jooble/Ireland (20 queries), Adzuna/gb with empty
location (10 queries), and existing result limits. Unknown providers can use the
rotating catalog (10 queries) or supply a custom query_plan. Empty registries run
nothing. Duplicate registry names fail before any factory is invoked.

A Lever/Ashby adapter can be registered without changes to DailyIngestionService.
It must return Job objects; a feed without keyword searches can supply a one-item
query plan and ignore the search terms in its adapter. No new network client exists.

### Results and safe failures

DailyIngestionResult.providers maps source_type to SourceIngestionResult.
Each result includes attempted queries_run, fetched, created, updated, unchanged,
failed_queries, status, error_code and duration_seconds. totals sums numeric counters.
Statuses are success, partial, failed or disabled. Query errors do not abort the
provider; setup/plan errors do not abort the remaining providers. No raw exception,
query text, credentials or provider payload is printed by the orchestrator.

The .jooble and .adzuna read properties remain for existing callers. The dataclass
constructor/serialized shape now uses providers, so asdict output from the CLI is
provider-agnostic. queries_run now includes failed attempts.

### Normalization and identity

JobObservation contains source_type, the external identifier and a normalized Job.
Job carries URL, title, company, location, remote, salary, description and raw_text.
IDs are namespaced by source; existing prefixed IDs are preserved. Text is stripped;
salary becomes text. Only HTTP(S) URLs without embedded credentials are accepted.
Scheme/host are normalized; path, query and fragment are retained since each can
identify a distinct vacancy. Provider parsers still determine remote/salary semantics.
Description is persisted by raw-job writes.

ID equality wins. For a previously unseen provider ID, exact stored URL equality
plus nonempty matching company, title and location permits reuse of a unique,
exclusively global job. Multiple matches are treated as ambiguous and not merged.
No title-only, fuzzy or AI matching is added. Personal jobs are not promoted by
global ID resolution. Redirects are not followed.

### Provenance, privacy and freshness

Each (job, source, global scope) or (job, source, user) observation is unique.
Rediscovery updates last_seen_at while retaining discovered_at. A canonical job
can keep alpha and beta observations independently. Provider payload metadata and
Gmail message IDs are not placed in shared provenance.

Global listings require a global observation. Candidate discovery requires a global
observation or an observation belonging to the user associated with that candidate.
Provenance listing returns global observations plus only the requested owner's
personal observations. This repository method is internal: authenticated user
selection remains the caller's responsibility.

Gmail/manual/import sources require user_id. Their existing ingestion paths are
preserved and exercised with local fixtures. Candidate analysis is not created by
global ingestion. Existing previously analyzed candidate relationships are untouched.

Archiving applies only to jobs with exclusively global observations, all older than
the cutoff. Personal observations preserve the previous exemption. Any fresh global
observation prevents archiving. Reimport clears archived_at even for unchanged job
content; maintenance can also reactivate observations newer than archived_at.

### Schema and parity

No new persistent table is introduced. Both database initializers upgrade provenance.
PostgreSQL retains the existing source_id scheme and partial unique indexes; legacy
composite primary keys are replaced using quoted catalog identifiers. Existing RLS
and policies are not changed. PostgreSQL schema work uses the bootstrap advisory lock.

SQLite upgrades the legacy NOT NULL user_id table by copying its observations inside
the initialization transaction, including freshness, then restoring lookup and
partial unique indexes. Existing rows survive repeat initialization. Production data
was not migrated during this task; tests used temporary SQLite databases and doubles.

Application DML uses ? placeholders, translated by PostgresConnectionAdapter.
Archiving uses portable COUNT(user_id)=0 instead of BOOL_AND.

## Launch 1B limitations

- No persistent provider-ID-to-canonical-ID alias map. A merged provider ID whose
  URL later changes cannot be reliably resolved; a separate record can result.
- Cross-provider redirect URLs, missing strong fields and ambiguous equivalences
  intentionally remain separate jobs. No historical duplicate cleanup is performed.
- Concurrent cross-provider imports can race on canonical resolution; there is no
  unique URL constraint or multi-observation transaction. Failed queries are isolated
  but successful writes within a partially failed query remain committed; counters
  describe completed queries, not a reconciled transactional ledger.
- Provider status is observable in the returned report/CLI, not a stored run history.
- Posted dates and arbitrary metadata are not persisted yet. Existing provider IDs
  remain on JobObservation but are not recorded per source after a cross-source merge.
- API pagination, source-specific freshness evidence for closed vacancies, retries,
  rate limits and Lever/Ashby adapters remain future work.
- Existing Adzuna currency/remote heuristics are preserved, not reinterpreted.
- Live PostgreSQL and provider behavior were not exercised. Tests use SQL doubles,
  fake HTTP responses and temporary SQLite; no external calls are required.
