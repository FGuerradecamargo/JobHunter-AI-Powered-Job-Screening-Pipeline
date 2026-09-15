# Launch 1D: scheduling and coverage

## Ownership audit

Previously run_daily_ingestion.py invoked global query rotation, user-owned
Gmail sync and age-only archive maintenance on every invocation. No repository
cron/workflow defines a deployment schedule. Global rotation uses 20 Jooble and
10 Adzuna queries per day index. Launch 1B stores shared employer boards;
Launch 1C supplies their lazy factories. GmailBackgroundSyncService enumerates
connected accounts and persists personal provenance; it is not a global board.

The new SourceScheduleService owns due decisions, claims and outcomes.
DailyIngestionService remains unchanged and provider-agnostic. Its injected
provider wrapper observes sanitized errors/skipped records and checks lease
ownership before/after fetching and before yielding each job for persistence.
Its existing importer still owns normalization, canonical IDs, sightings and
reactivation. A source failure does not stop other sources. A database/system
failure is systemic and stops the CLI with a safe error code.

## Persistent state

source_ingestion_state has one row per execution identity: active_run_id,
lease_expires_at, next_eligible_at, last_attempt_at and last_success_at.
source_ingestion_runs contains immutable run identity/source association,
timestamps, status, fetched/created/updated/unchanged counts, failed_queries,
sanitized error_code, next_eligible_at, coverage_complete and duration_seconds.
Only its active run is finalized. No candidate IDs, subscriber identities,
URLs, credentials, response bodies or generic metadata are stored.

Both schemas are created idempotently alongside the company registry for
SQLite and PostgreSQL. Existing records/schema are preserved. PostgreSQL RLS is
enabled with no client policies, consistent with the existing backend-only
tables. The scheduler requires the same trusted backend database role.

## Claims

Acquisition uses an atomic conditional UPDATE inside the database transaction,
not a process-local lock. A live lease blocks competing workers; not-due rows
also block acquisition. The default lease is one hour. Queries and individual
job iteration renew it only while the run still owns an unexpired lease.
Expired claims can be replaced; the abandoned run becomes expired/incomplete.
Finalization is fenced by run ID and expiry and atomically releases the claim
while setting next eligibility. A late worker cannot finalize a newer run.

As with time-limited leases, an old network request cannot be forcibly aborted
after lease loss. Its returned batch is rejected before import. An already
executing single database write may finish, but stale runs never supply absence
evidence. Sightings only make archiving more conservative. Set worker/network
deadlines below the lease, and alert on expired runs. This is not a distributed
exactly-once external HTTP guarantee. Tests exercise competing connections and
stale-worker fencing without sleeps.

## Deterministic policy

SchedulePolicy defaults:

| Outcome | Next eligible |
| --- | --- |
| Global success | 24 hours after completion |
| Employer success | 6 hours after completion |
| Transport/generic query failure | 30 minutes |
| Rate limit | 120 minutes |
| Setup/shape/pagination/resource failure | 6 hours |
| Partial/degraded | 60 minutes, unless a higher-specificity error applies |

All values must be positive and are configurable through SchedulePolicy.
There is one attempt per due source per scheduler invocation. Connector-local
finite retries remain unchanged. No scheduler sleep/retry loop or AI decision.
The day index determines query rotation, never bypasses due/claim checks.

All enabled supported company registry rows are polled, including boards with
no subscribers. Watchlists are not read to generate per-user work. Multiple
candidates monitoring a company share its one source row/global fetch. Registry
IDs and board assignments should remain stable; changing a board should use a
new source row rather than repointing an old identity with old coverage history.

## Coverage and archive safety

Lever/Ashby success with exactly one completed full-board query, no skipped
records and successful import is coverage_complete=1. Setup/fetch/page/import
errors, lost leases, malformed/unlisted skipped records are incomplete. Valid
siblings may still be imported in a degraded run. Global keyword samples never
claim complete board coverage, even when every planned query succeeds.

Age-only archiving is removed. A job can be archived only when *every* provenance
source satisfies the conservative rule: no personal observations; last sighting
older than the configured age (default 30 days); enabled employer source; no
active claim; latest attempt successful/complete within 48 hours; and at least
two complete runs started after the last sighting. Disabled, stale, unknown,
sampled-global, error or degraded sources protect the job. A failure contributes
zero absence evidence and blocks archive until a later complete latest run.
No per-job absence table is needed: run history plus sightings provides this
evidence. Existing import and reactivation maintenance unarchive reappearances.

This intentionally retains more jobs, including those with mixed global-query
provenance. The earlier Source V2 age-only test now checks that old sightings
alone do not archive; its reappearance behavior remains covered. Run history
must not be pruned without preserving the evidence needed by this policy.

## Operations

```text
python run_source_scheduler.py
```

Initializes schema, executes due global and employer sources, then performs
conservative archive maintenance. Outputs JSON. Exit 0 includes isolated source
failures; exit 1 means systemic failure. Suitable for an external periodic
runner; no hosted cron is created or bound to a vendor. Streamlit Cloud does
not acquire scheduling responsibility merely by deploying this CLI.

The existing run_daily_ingestion.py delegates API work to the same scheduler,
preserving --skip-apis, --skip-gmail, result counts and query day-index options.
Gmail remains explicitly separate there; the new scheduler never calls Gmail.
Avoid enabling both entry points for Gmail without a separate Gmail concurrency
policy. No user-facing UI is added.

## Limits and Launch 1E

Launch 1E can validate operational coverage through persisted runs/state and
structured CLI results without an architecture change. Live PostgreSQL,
production credentials, deployment cadence and actual board completeness still
need controlled operational validation. Tests use SQLite and PostgreSQL-adapter
SQL doubles, not a live database service. Skipped-record counts are observed to
degrade coverage but not persisted individually. Existing import failures can
leave safe sightings with underreported counts; they never grant coverage.
Retention, alerts, a monitoring UI and direct vendor closure evidence remain
future work. No AI or external network is used during implementation/tests.

## Files and validation

Added: source_run_schema.py, source_run_repository.py, source_schedule_service.py
under services; run_source_scheduler.py; tests/test_source_scheduler.py; this doc.
Updated: services/database.py, services/job_archive_service.py,
run_daily_ingestion.py and tests/test_source_v2_foundation.py.

Validation: 33 Launch 1D cases; 209 combined scheduler/Launch 1A-1C tests;
14 archive/freshness cases; 85 authentication/isolation/Gmail tests;
full suite 1111 passed, 2 skipped. Outbound sockets and DNS were blocked in
test processes. No live API, AI call, commit or push was performed.
