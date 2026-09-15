# Launch 1F: Adzuna and Jooble Validation Preflight

Date: 2026-09-15. Branch: `feature/postgres-migration`, HEAD `7f6d9bd`.

## Decision: NOT READY

The Launch 1E gate remains unchanged. Live execution stopped at credential
preflight, as required. There is no new evidence supporting a readiness upgrade,
and no evidence that an additional connector is necessary.

Smallest next action: securely configure `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` and
`JOOBLE_API_KEY` in the local validation environment, then repeat bounded live
validation. Do not paste credentials into chat or commit secret files.

## Configuration Audit

The environment plus local dotenv lookup returned presence booleans only:

| Variable | Present and nonblank |
| --- | --- |
| ADZUNA_APP_ID | no |
| ADZUNA_APP_KEY | no |
| JOOBLE_API_KEY | no |

An additional inspection of standard Streamlit secrets files was blocked by
the tool approval mechanism. Those files and Community Cloud configuration are
**unverified**; the environment check is not evidence about Cloud secrets.

Both source constructors use `load_dotenv()` then `os.getenv()`. Neither directly
reads `st.secrets`. They have no hardcoded credential fallback. A standalone
validation process must have environment/dotenv configuration available.

| Setting | Adzuna | Jooble |
| --- | --- | --- |
| Constructor default | country `ie` | no country argument |
| Production registry | country `gb`, location empty | location `Ireland` |
| Daily rotating query limit | 10 | 20 |
| Default results per query | 20 | 20 |
| Request method | GET | POST |
| Timeout | 30 seconds | 30 seconds |

Rotation uses `(day_index * limit) % catalogue_size`. The default Jooble plan
must not be invoked unchanged for this slice: twenty requests exceed the
suggested live budget. A future validation must inject a bounded query plan,
reserve repeat requests within that same budget, and explicitly select IE/GB
Adzuna instances. Default registry settings do not validate both countries.

The scheduler sets successful global sources due again after 24 hours. These
are sampled query sources, never complete employer-board coverage. Current
failure policy is 30 minutes generally, 120 for rate limiting and 360 for setup
failures. No scheduling policy was changed.

## Credential Safety Findings

Adzuna supplies credentials as query parameters; Jooble includes its key in the
request path. Direct `raise_for_status()` and transport exceptions can contain
credential-bearing URLs. Do not print exceptions, response/request objects or
raw URLs from these adapters. The existing ingestion/scheduler boundary emits
sanitized categories instead of exception strings; future live validation must
retain that boundary and suppress raw tracebacks. No live call was attempted.

Two interpretation risks found by inspection, not live measurement:

- Both adapters set remote based on the substring `remote`, including potentially
  negated descriptions. A remote survivor is not confirmed remote eligibility.
- Adzuna labels salary GBP regardless of its country argument. IE salary
  interpretation needs care. Salary was not a Launch 1E threshold.

No production change was made for these findings in this validation-only slice.

## Live Metrics

| Metric | Adzuna | Jooble |
| --- | --- | --- |
| Live requests attempted | 0 | 0 |
| Live requests successful | 0 | 0 |
| Jobs fetched/valid/skipped | not measured | not measured |
| Created/updated/unchanged | not measured | not measured |
| Duplicate records/cross-source merges | not measured | not measured |
| Duration/errors | no request executed | no request executed |
| Coverage semantics | sampled queries | sampled queries |

No employer-board refresh was performed. No new shared pool was built. Incremental
contribution, aggregator overlap, second-pass IDs and freshness remain unverified.
The historical 69-job employer sample is not a newly observed current pool.

## Unchanged Profiles and Thresholds

Exact definitions remain in `scripts/validate_launch_coverage.py`. No profiles or
thresholds were changed: 20-50 plausible, 5-15 deterministic survivors and later
2-5 genuinely attention-worthy jobs. Deterministic survival is not final fit.

Launch 1E pool/discovery counts were 69 for every profile. The table preserves
those historical measurements; unknown after-values are not substituted with zero.

| Profile | 1E title / location-mode / survivors | 1F after adding aggregators |
| --- | --- | --- |
| IE customer operations/support | 1 / 0 / 0 | unverified |
| IE fraud/risk/trust | 6 / 0 / 0 | unverified |
| IE fintech/payment operations | 2 / 0 / 0 | unverified |
| IE analyst | 4 / 1 / 0 | unverified |
| UK operations management | 4 / 3 / 3 | unverified |
| UK customer success | 1 / 1 / 1 | unverified |
| UK compliance/AML | 4 / 4 / 4 | unverified |
| UK remote support | 1 / 0 / 0 | unverified |
| Europe remote fintech/risk | 8 / 2 / 1 | unverified |
| Europe customer success/analyst | 5 / 4 / 1 | unverified |

## Bottleneck and Offline Evidence

Immediate blocker: validation configuration, not proven aggregator recall.
Launch 1E showed sparse sample coverage for IE/remote support **and** filtering
limitations (generic analyst false negatives, broad risk/operations false
positives). This slice cannot determine how much the aggregators resolve the
source-coverage gap. Do not conflate those separate problems.

Offline regressions exercised both actual adapter parsers using fake responses,
Source V2 dedupe/freshness, scheduler claims/backoff/failure isolation/not-due
skips, Launch 1E criteria and authentication/user isolation. No real API behavior
is inferred from these doubles. PostgreSQL live validation remains pending.

- Focused regressions: **132 passed in 14.42s**, socket/DNS blocked.
- Full suite: **1123 passed, 2 skipped in 28.68s**, socket/DNS blocked.
- `git diff --check` passed; new report also checked with `--no-index`.
- Zero external requests, zero AI/Gmail calls during this slice.
- Only this report added; no production code, secrets, schema or UI changes.
- No commit or push.
