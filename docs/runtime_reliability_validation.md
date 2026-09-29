# Runtime reliability validation

## Profile readiness

`ProfileReadinessService` compares confirmed onboarding/career-update input with
the official snapshot schema and source signature. Candidate presentation text
is not a readiness authority. Product mode and commercial access remain separate.

The Profile action explicitly generates a missing snapshot through the existing
validated interpreter. `backfill_missing` preserves Candidate and snapshot history,
reuses an existing snapshot, and accepts a concurrent insert winner. Stale snapshots
require explicit regeneration, not a silent migration. No bulk production backfill
is executed on page load. The explicit generation action can use the configured AI
client; tests inject fakes. Generating a snapshot does not imply recommendation
sufficiency or proven capability where evidence is unknown.

## Measurements

The `workpilot.timing` logger emits `page`, `block`, `elapsed_ms`, and `outcome`.
Blocks include auth.session, profile.readiness, profile, applications,
opportunities, opportunities.search_unit, and market. Each connection.execute /
executemany call records a database.query block. SQL and parameters are not logged.
Execution timings do not separately measure cursor fetching or pool acquisition;
enclosing block timings include that overhead. Nested durations must not be added
as if they were independent. Initial shell authentication is labeled shell;
page/fragment work carries its page title. These are measurements, not a claim
that production latency has improved.

`workpilot.oidc` logs allowlisted stages and outcomes without claims or exception
text. Callback means the application observed Streamlit's authenticated OIDC user;
failures inside Streamlit's native callback before that point still need sanitized
platform diagnostics. No native tokens are inspected or logged by WorkPilot.

## Browser verification still required

- Refresh Jobs, Applications and Profile with a valid cookie and empty browser
  session state; also repeat with an expired cookie. No private page may run before
  server session validation.
- Start and stop a controlled search. Only its fragment should rerender between
  units; the terminal update refreshes saved results once. In-flight work may finish.
- Load Dashboard: market is not requested until its explicit load control is used.
- Open application details and interact with its controls on subsequent reruns.
- Exercise Google sign-in and correlate the last safe OIDC stage with platform logs.
- Inspect Sources link contrast on desktop/mobile and check Gmail's email/job units.

No production measurements, backfill, Google login, Gmail sync, or real AI search
were performed as part of the offline implementation.
