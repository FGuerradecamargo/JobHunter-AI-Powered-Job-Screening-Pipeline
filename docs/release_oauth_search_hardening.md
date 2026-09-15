# Gmail callback and cooperative search

## Gmail production redirect

Gmail's OAuth flow sends the browser to the configured
`GOOGLE_OAUTH_REDIRECT_URI`. The callback lives on Sources, not the dashboard.
Configure the top-level production secret (or environment variable) and the
Google OAuth client's authorized redirect URI to exactly:

```text
https://<CANONICAL_STREAMLIT_HOST>/Sources
```

Use the actual production hostname if it changes. Match scheme, hostname,
case-sensitive route, and trailing slash exactly. Do not use the app root,
another deployment's hostname, a preview URL, query parameters, or a fragment.
Local development uses `http://localhost:8501/Sources` with its own authorized
redirect entry. This Gmail consent callback is separate from Streamlit Google
sign-in's `/oauth2callback` endpoint; do not replace the sign-in redirect.

The previous completion path only called `st.rerun()`, leaving navigation
implicit. Completion now clears callback parameters and switches explicitly to
the fixed local page `pages/2_Sources.py`; the router pins its URL to `Sources`.
No callback-supplied URL is accepted as a destination. State consumption,
initiator binding, PKCE exchange and connection persistence are unchanged.
Invalid state or errors do not take the success navigation path.

A wrong configured hostname still sends the browser to that wrong deployment
*before* our callback executes. Local code inspection cannot verify deployed
secrets or Google's authorized URLs. The deployment configuration must be
checked separately; a local page switch cannot repair a wrong-host callback.

## Search execution and cancellation

Opportunities screens the existing shared catalog, not live provider queries.
The target (5/10/15 accepted opportunities) limits activation, not the number
of rejected jobs examined. DailyIngestionService independently iterates provider
query plans, with results_per_query passed to JobImportService. Those shared
scheduled imports and Gmail sync are not owned by a candidate's search and are
not cancelled by this control.

Previously a synchronous while loop processed waves of ten jobs without
returning control to Streamlit. It is now incremental:

1. Explicit Find action creates a session-local run and immutable scan ID.
2. First unit activates previously completed worthwhile analyses up to target.
3. Each subsequent unit selects at most one job, ensures its candidate link,
   calls analyze_pending for that job, then merges results and activates it.
4. Partial results and Stop search render before the next unit. The page calls
   st.rerun after one unit, so queued widget callbacks execute before further
   work. There is no blocking multi-job loop, worker thread or heartbeat.
5. Stop marks that run stopped. Future advances do nothing. Results remain in
   the existing candidate-job tables; nothing is rolled back or deleted.

The cancellation boundary is one complete job analysis/persistence unit, not
an HTTP request. Such a unit can include description enrichment, job-profile
generation and candidate batch analysis (now containing one job). A queued Stop
click is observed at the next rerun, after this unit finishes; those in-flight
costs may still occur. No future job or AI unit starts after Stop is observed.
The unit emits no Streamlit UI output: persistence and counter merging finish
before the next interruptible UI boundary. Existing analysis claim release
remains in analyze_pending's finally block.

Required runtime setting: `.streamlit/config.toml` sets
`[runner] fastReruns = false`. Streamlit's fast-rerun mode could otherwise
replace the runner while an earlier unit is still in flight. Start Streamlit
from the repository root so this config is loaded; do not override it with
`STREAMLIT_RUNNER_FAST_RERUNS=true`. The page refuses new searches if the
effective setting is true. This setting queues interactions app-wide until
the current script reaches a yield point, instead of replacing its thread.

Run scope includes authenticated actor, active user, candidate and profile
signature. A changed scope discards the old run; stop callbacks also require
the exact scan ID. Tabs have separate search runs, including for one candidate;
there is no process-global cancellation flag. Logout/session expiry discards
the run. Database analysis claims continue protecting concurrent analyses.
New searches get new IDs and budgets, independent of prior stops. Errors stop
automatic advancement with a safe message and retain partial results; they
are not automatically retried. Provider quota/no-progress still end the run.

Trade-off: single-job analysis increases rerun overhead and may lose batching
efficiency. Browser/page closure pauses this session-local run; this is not a
durable background search system. No schema changes are needed.

Tests use fake repositories, clients, page callbacks and a queued-rerun model.
No production callback, paid generation or live provider request is required.
