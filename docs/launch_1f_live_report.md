# Launch 1F Resumed: Live Validation

Date: 2026-09-15. Branch `feature/postgres-migration`; baseline `e9984c1`.

## Decision: NOT READY

Jooble improves the measured Ireland supply, but none of the unchanged ten
profiles reaches five deterministic survivors. Adzuna rejected every request
with HTTP 401; its market coverage remains unknown, not empty. Do not add a
connector based on this result.

**Smallest next action:** correct/verify the Adzuna credential pair and account
authorization, then authorize a single smoke request before another batch.
Separately, the generic analyst filtering problem is now reproduced on real
source observations and merits a narrowly scoped fix. Do not lower thresholds.

## Safety and Scope

All three required environment/dotenv values were present and nonblank;
`.env` is gitignored. No secret values were printed or retained in evidence.
The user confirmed Jooble scope as Ireland; no UK Jooble request was made.

Actual collection: 2026-09-15 19:50:45-19:50:59 UTC. Ten Adzuna requests and six
Jooble requests, each below the twelve-request limit. No redirects or retries.
The predetermined plan included repeat requests even after Adzuna 401 responses;
no further diagnostic requests were made. Future runs should stop early on
authorization failures instead of spending the remaining query budget.

Validation-only HTTP wrapper enforces the provider host, HTTPS, request count,
response size and timeouts; disables ambient proxy/netrc configuration; and
discards raw exception strings. CLI logging and raw tracebacks are suppressed.
Evidence removes URLs and redacts credential strings. Actual adapters parse the
responses, and actual Source V2 import/scheduler code ingests their results.

All database work used temporary SQLite, deleted on completion. No real
candidate, production DB, production registry or production code was changed.
No OpenAI/LLM, Gmail or LinkedIn requests. No commit or push.

Evidence: [sanitized measurements](validation/launch_1f_live_evidence.json).
Only metrics and short title/company/location examples are retained, not raw
descriptions or request/response objects. PostgreSQL live validation is pending.

## Provider Metrics

| Provider/market | First + repeat requests | Successful | First raw/valid | Repeat raw/valid | Errors |
| --- | ---: | ---: | ---: | ---: | --- |
| Adzuna IE | 4 + 1 | 0 | 0/0 returned | 0/0 returned | five HTTP 401 |
| Adzuna GB | 4 + 1 | 0 | 0/0 returned | 0/0 returned | five HTTP 401 |
| Jooble Ireland | 4 + 2 | 6 | 59/59 | 19/19 | none |

Adzuna failures do not establish absence of jobs. Malformed/skipped counts are
unknown for failed requests. Jooble skipped zero records and returned no duplicate
IDs *within each response*. Query/duration/timestamp details are in the evidence.
Adzuna IE elapsed request time summed to 4.579s; GB 4.499s; Jooble 3.985s.

Queries, page 1, twenty requested results each:

- IE: `customer support`, `fraud risk`, `payments operations`, `analyst compliance`.
- GB Adzuna: `operations`, `customer success`, `compliance AML`, `remote support`.
- Repeats: Adzuna IE support and GB remote support; Jooble IE support and analyst.

Jooble first response sizes/unique IDs per query: 12, 20, 20, 7. The union after
canonical import was **40 jobs**, all with Jooble provenance. First-pass import:
40 created, 7 updated, 12 unchanged. The 19 excess observations relative to the
40-row pool are 32.2% of 59 fetched observations; this is query overlap/reuse,
not a measured false-duplicate rate. Updated content may be query-dependent;
the raw descriptions were intentionally not retained to diagnose that further.

Both providers are sampled query sources. `coverage_complete` stays false.

## Repeatability and Dedupe

Jooble repeated support retained 12/12 IDs; analyst retained 7/7. The repeat
import produced 19 unchanged, zero updates and zero new rows. All initial
canonical IDs remained, with 40 provenance rows. Eighteen distinct provenance
rows advanced `last_seen_at` (nineteen observations can overlap on one job).
There was no duplicate flood in this subset. This seconds-apart check is not
evidence of daily freshness or long-term reliability.

Cross-provider shared canonical jobs: zero observed, because Adzuna supplied
no jobs. This is **not** a validation of Adzuna/Jooble overlap. No retained pool
rows had equal normalized title/company/location signatures; differently worded
duplicates remain possible. No false merge was demonstrated, but the live
measurement did not retain an external-ID-to-canonical-ID audit map sufficient
to distinguish every same-provider ID reuse from an exact canonical merge.
Conservative exact/ambiguous/tracking-query cases passed offline regression.

## Historical Employer Baseline

Launch 1E retained aggregate metrics and selected examples, not all 69 job
records/descriptions. The historical sample cannot be reconstructed faithfully
for combined filtering or cross-source dedupe. Employer boards were **not**
re-fetched. Their 69 jobs are historical evidence, not a current live pool.

Therefore 1F pool size is **40**, not 109. Its measured provider contribution is
Jooble 40, Adzuna 0 returned. Incremental unique contribution relative to the
historical employer set and aggregator-to-board merges remain unverified.

## Exact Profile Comparison

T/P/S = title plausible / location-mode plausible / deterministic survivors.
1E pool was 69; 1F aggregator-only pool is 40 for every row. Profiles and working
thresholds were unchanged: 20-50 plausible, 5-15 survivors, later 2-5 genuinely
attention-worthy. No final match quality or human-attention count is claimed.

| Profile | 1E T/P/S | 1F T/P/S | 1F assessment | Main observed bottleneck |
| --- | --- | --- | --- | --- |
| IE support/operations | 1/0/0 | 2/2/2 | weak | SOURCE COVERAGE/sample recall |
| IE fraud/risk/trust | 6/0/0 | 2/2/1 | weak | MIXED: few roles and seniority eligibility |
| IE fintech/payment operations | 2/0/0 | 1/1/0 | insufficient | MIXED: only director-level match |
| IE analyst | 4/1/0 | 7/7/0 | insufficient | FILTERING / ELIGIBILITY |
| UK operations management | 4/3/3 | 0/0/0 | insufficient | SOURCE COVERAGE unverified: Adzuna 401 |
| UK customer success | 1/1/1 | 0/0/0 | insufficient | SOURCE COVERAGE unverified: Adzuna 401 |
| UK compliance/AML | 4/4/4 | 2/0/0 | insufficient | SOURCE COVERAGE unverified: only IE results |
| UK remote support | 1/0/0 | 2/0/0 | insufficient | SOURCE COVERAGE unverified: only IE results |
| Europe remote fintech/risk | 8/2/1 | 3/0/0 | insufficient | MIXED: sparse sample/work-mode eligibility |
| Europe success/analyst | 5/4/1 | 7/7/0 | insufficient | FILTERING / ELIGIBILITY |

UK zeros are not evidence that the 1E jobs disappeared or that the UK market
lacks roles. Comparisons are separate samples, not before/after of one merged DB.
All nonzero 1F counts come from Jooble; Adzuna adds no measured candidates.

Concrete diagnostics:

- Support survivors: `Remote- Customer Support Specialist` (Nexora Talent) and
  `Customer Service Representative` (Dynamics ATS), both labeled Ireland.
  These labels and source snippets do not establish work authorization or quality.
- `Financial Crime Advisory Consultant` survives risk matching. `Director,
  Technology Risk` is rejected for seniority; technical risk is also only adjacent
  to operational fraud/trust. Broad keywords still permit false positives.
- `Business Operations Director` is the sole IE operations title match and is
  appropriately rejected for seniority, not proof of an overly strict filter.
- Seven analysts are rejected for direction, including `PMO Analyst`, `Contract
  Analyst II` and `Business Analyst - Trade Finance / Contingent Liabilities`.
  Generic analyst tokens are removed by existing direction matching. Some other
  technical analyst roles may be unsuitable, but rejecting every analyst is a
  filtering signal, not zero source supply.
- Current adapters infer remote from a substring, including potentially negated
  text. This rule was not changed; remote eligibility remains provisional. Jooble
  may also substitute requested location when the payload lacks it. Therefore
  geographic plausibility is not verified employer eligibility.
- Adzuna IE currency labeling remains a known inspection finding (GBP hardcoded),
  not live-observed here. Salary is not used in these profile thresholds.

## Scheduler and Tests

Scheduler used actual collected-job replays in isolated SQLite. Both initial
claims succeeded; Adzuna failed without blocking Jooble. Adzuna next eligibility
was +30m, Jooble +24h. Immediate invocation skipped both as not due. A simulated
+25h enabled the repeat replay. Actual collection timestamps are distinct from
simulated scheduler timestamps. All completion flags remained false.

- Focused regressions: **140 passed in 16.91s**, with socket/DNS blocked.
- Full suite: **1131 passed, 2 skipped in 30.85s**, socket/DNS blocked.
- `git diff --check` passed; new files also checked with `--no-index`.

Changes: validation-only script, eight safety/fake-client tests, sanitized live
evidence and this report. Earlier preflight report is retained as history.
