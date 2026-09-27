# Job observation authority cutover

The existing JobSourceRepository now owns the atomic observation/identity/content
write. JobImportService, GmailJobProcessor and the Sources manual form use it.
No additional parallel ingestion service was introduced; the preserved WIP branch
was inspected, not merged.

## Authority and identity

- Private observations have owner/source/identity-scoped IDs. They may attach to an
  exactly matching public job, but cannot replace that job's public content.
- Exact public URL plus title/company/location corroborates shared identity.
  Known tracking parameters are removed; meaningful queries and fragments remain.
  Conflicting identity fields isolate collisions rather than overwrite a job.
- Public observations choose content deterministically by provenance: fetched
  canonical job page first, then source namespace/external ID. This tie-break is
  not a claim that one provider's assertions are verified truth.
- The selected source can correct to shorter text. Length has no authority.
- Source observations retain their own payloads. Unknown fields remain unknown.
- Migration does not backfill legacy authority. A fresh independently eligible
  public observation can establish it after exact identity resolution.
- Already private-only jobs are not retroactively merged into public records;
  preserving candidate history takes precedence over speculative deduplication.

## Persistence and compatibility

`migrate_job_observations.py` applies additive idempotent tables and server-only RLS
for PostgreSQL. Normal database initialization includes the same schema function.
It does not rewrite existing jobs, candidate analyses or lifecycle records.
Do not run against production without migration approval.

`upsert_raw_job` is insert-only compatibility. Candidate-specific enrichment can
persist a fetched description only through the public authority/URL check.
The obsolete global recommendation JSON importer (`sync_database.py`) now exits
without bootstrap or writes; its database writer functions were removed after
the complete caller search.

The official profile service can load literal fields through
`JobSourceRepository.load_job_hard_facts`. Private inputs require the owner's ID;
private observations never change public profile signatures. These fields are
source facts, not AI-extracted mandatory requirements. The old production
JobProfileManager still requires the next runtime caller replacement.

## Validation boundary

Offline tests reproduce the former cross-user overwrite, two public sources,
ordering, collisions, tracking links, shorter corrections, Gmail retries,
ownership, source deletion, rollback and snapshot history. SQLite exercises real
transactions; PostgreSQL SQL doubles check RLS shape, not real server execution.
No production migration or provider/AI call was performed.
