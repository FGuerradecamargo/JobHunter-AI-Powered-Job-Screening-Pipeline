# Job observation authority

This change fixes private imports overwriting shared vacancy content. It does not
repair or reclassify historical production data, change authentication, or change
candidate analyses/application lifecycle records.

## Rules

- Gmail and manual imports always carry an owner. Their full imported content is
  stored in `job_observations`, scoped by user, source, external ID and URL.
- A private observation may reference an existing public vacancy only when URL,
  title, company and location match. It never supplies public canonical content.
- Without that match, a private, owner/source-namespaced job projection is created.
  Two private imports alone do not establish trusted public facts and are not
  merged across owners. Existing private projections are not silently remapped
  when a public vacancy appears later; this preserves lifecycle references.
- Public ingestion explicitly opts into public authority. This is an internal
  capability of the operator-configured provider importer, not a payload field.
  Personal source types cannot opt into it. A non-null owner remains private even
  if the source is named after a public provider.
- New public vacancies select canonical content deterministically by ascending
  `(source_type, external_id, observation_id)` among public observations. This is
  a stable provenance tie-break, not a claim that longer text is more trustworthy.
  The selected source can refresh its own data. Other observations remain stored.
- Known tracking parameters are removed for matching. Vacancy query parameters,
  path case and fragments are preserved. Different provider namespaces do not
  share an identity merely because external IDs match. Conflicting identity
  metadata is not merged by URL alone.
- Legacy rows have no inferred content authority: their existing content is frozen.
  An unprovenanced ID collision cannot promote an orphan job into the public pool.
- `upsert_raw_job` and the dormant recommendation import cannot overwrite existing
  jobs. Enrichment only fills an empty description for a proven public canonical
  record at the same URL. JobProfile generation itself is unchanged; its inputs
  now come from isolated private projections or canonical public content.

## Atomicity and scope

Job creation, observation, source association and authority selection commit in
one transaction. PostgreSQL uses transaction advisory lock 731304; SQLite uses
`BEGIN IMMEDIATE`. The short database operation is serialized, not provider calls.
An email retry after commit reuses its observation and job. Failure before commit
rolls back all four records. Private reads require an owner predicate. The new
tables use server-only RLS on PostgreSQL and revoke public/PostgREST role access.
Removing one user's source does not delete a job or another user's source.

## Migration and rollout

`python migrate_job_observations.py` is the explicit, idempotent additive migration
for an existing database. Normal schema initialization also registers these two
tables, consistently with existing fresh-database/bootstrap behavior. Run the
migration under the existing backend database role before deploying the code.
No production migration was executed during implementation.

The migration creates `job_observations`, its owner index, and
`job_content_authority`. It does not backfill payloads, change job IDs, delete rows,
or update candidate/application/interview records. New private IDs intentionally
differ from the old unscoped IDs. Do not rewrite historical references automatically.
Existing contaminated rows require a separately approved investigation/cleanup.
Legacy canonical refresh remains frozen until a separately reviewed provenance
backfill is available; this favors integrity over guessing ownership.

The PostgreSQL SQL/parameter/lock path is tested offline with an adapter double;
actual PostgreSQL integration must be validated on an isolated non-production
database before rollout. Never roll back to the vulnerable writer with live imports
enabled. Added tables can remain in place during application rollback.

## Write-path review

- Gmail, manual Sources UI, provider/user JobImportService: routed through observations.
- `database.upsert_raw_job`: insert-only compatibility writer.
- `database.upsert_recommendation`: dormant legacy import, conflict updates removed.
- `database.update_shared_job_analysis_data`: restricted public enrichment fill.
- Archive/reactivation/status/note writers: lifecycle operations, not content authority;
  unchanged except public reobservation reactivation stays in the import transaction.
- `JobProfileManager`: separate derived cache, no direct jobs write; unchanged.
- `candidate_job_analysis_service_HEAD_backup.py`: dormant copy calling the now guarded
  enrichment helper; no separate content-write bypass found.
