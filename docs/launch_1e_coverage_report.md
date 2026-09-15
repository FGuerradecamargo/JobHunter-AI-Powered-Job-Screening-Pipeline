# Launch 1E: Coverage Validation

Date: 2026-09-15. Branch: `feature/postgres-migration`. Baseline: `759a0d9`.

## Decision: NOT READY

The measured sample does not demonstrate launch-quality coverage for the ten
representative profiles. None reaches five deterministic survivors; five have
none. This is a gate on the evidence collected, not a claim that the entire
Source V2 architecture cannot provide sufficient coverage.

**Smallest next action:** supply Adzuna/Jooble configuration in an isolated
validation environment and repeat bounded IE/UK queries. Also verify the current
public board for Plaid before enabling that registry entry. A new connector is
not yet proven necessary: the existing global sources were unavailable locally.
Do not commission another ATS connector based on this four-board sample alone.

## Method and Safety

- Ten synthetic profiles, no personal records or candidate CVs.
- Mid-level, English-speaking; no night shifts, mandatory relocation or
  overnight on-call. Role terms and markets are recorded in the JSON evidence.
- Hybrid preferred but onsite considered, except two remote-required profiles.
- Live reads: eight public GET requests total, under a twelve-request cap,
  two observations per board. Existing allowlisted connectors perform parsing.
- Collection occurred at 13:52:59-13:53:09 UTC. Observations seconds apart establish
  repeatability, not daily freshness or an uptime SLA.
- The real scheduler/import/repository code consumed the collected jobs through
  in-memory replay providers in temporary SQLite. Second scheduler time advanced
  eight hours without sleeping. Scheduler timestamps after collection are
  simulated; provider `observed_at` timestamps are actual wall time.
- Temporary DB removed after the run. Production DB and registry unchanged.
- No OpenAI/LLM, Gmail, downstream analysis, paid global API or LinkedIn calls.
  Public board selection also used web search; the eight-request number counts
  connector GETs, not those preliminary public searches.
- PostgreSQL live validation pending. Adapter/schema doubles are not live proof.
- Evidence: [machine-readable observations](validation/launch_1e_evidence.json).
  No full descriptions, credentials or real user data are retained there.

## Provider Results

Counts below are per observation; both observations returned the same counts.
Created/updated/unchanged refer to local ingestion of the real observations.

| Source | Live result | Raw / valid / skipped | First C/U/N | Second C/U/N | Complete | HTTP durations, seconds |
| --- | --- | --- | --- | --- | --- | --- |
| Lever Zopa | 2/2 success | 34 / 34 / 0 | 34/0/0 | 0/0/34 | yes | 2.079 / 2.328 |
| Lever Plaid | 0/2 success; `http_status` | 0 / 0 / 0 | 0/0/0 | 0/0/0 | no | 0.968 / 1.360 |
| Ashby Paddle | 2/2 success | 19 / 19 / 0 | 19/0/0 | 0/0/19 | yes | 0.703 / 0.593 |
| Ashby Wayflyer | 2/2 success | 16 / 16 / 0 | 16/0/0 | 0/0/16 | yes | 0.672 / 0.578 |
| Adzuna | unverified; local credentials absent | unknown | n/a | n/a | unknown | n/a |
| Jooble | unverified; local credentials absent | unknown | n/a | n/a | unknown | n/a |

Plaid's sanitized failure does not establish whether the board moved, was
removed or was denied. Do not classify its zero as an empty successful board.
Do not generalize that failure to every Lever employer.

Zopa supplied UK banking/compliance/operations examples (London and Manchester).
Paddle supplied technology/payments board coverage, including a UK/Netherlands
team-lead example; a remote label alone does not imply Ireland eligibility.
Wayflyer supplied fintech roles, including London account management and risk.
The boards were selected for market/sector relevance, not randomized sampling.
Reliability observed: 6/8 successful requests, with both failures on one board.
No provider-wide long-term reliability estimate is justified.

## Profile Coverage

Shared pool and initial discovery eligibility were **69 for every profile**.
Title count precedes geographic/work-mode checks. Plausible count includes them.

| Synthetic profile | Title plausible | Location/mode plausible | Hard-filter survivors | Assessment |
| --- | ---: | ---: | ---: | --- |
| Ireland customer operations/support | 1 | 0 | 0 | insufficient |
| Ireland fraud/risk/trust | 6 | 0 | 0 | insufficient |
| Ireland fintech/payment operations | 2 | 0 | 0 | insufficient |
| Ireland analyst | 4 | 1 | 0 | insufficient |
| UK operations management | 4 | 3 | 3 | weak |
| UK customer success | 1 | 1 | 1 | weak |
| UK compliance/AML | 4 | 4 | 4 | weak |
| UK remote support | 1 | 0 | 0 | insufficient |
| Europe remote fintech/risk | 8 | 2 | 1 | weak |
| Europe customer success/analyst | 5 | 4 | 1 | weak |

Working targets: 20-50 plausible, 5-15 deterministic survivors, 2-5 genuinely
worth attention. For this diagnostic, strong means >=20 plausible and >=10
survivors; acceptable means >=5 survivors; weak means 1-4; insufficient means 0.
These labels measure coverage potential only. Genuine attention-worthiness is
**unverified**, not zero and not equal to the survivor count. Counts across
profiles overlap and must not be summed as unique jobs.

The existing `HardFilterAnalyzer` was used with literal title-only `JobProfile`
inputs, not AI-generated capabilities. No work authorization, detailed experience
or final suitability was inferred. Geography is an additional validation-only
regex allowlist of country/city labels, not a new production filter. It is
incomplete; Europe/EMEA and multi-location labels still require eligibility review.
Remote requires an explicit true flag; unknown/hybrid is not treated as remote.

### Obvious Limitations

- Initial discovery is broad by design: role-family affinity orders jobs, it
  does not exclude them. All 69 jobs entered each synthetic discovery query.
- Generic `analyst` direction loses meaningful tokens in the existing filter;
  one IE and three Europe plausible analyst jobs were rejected for direction.
  These are potential false negatives, not evidence of zero analyst supply.
- `Senior Credit Risk Data Scientist` survived the broad remote risk profile:
  risk keywords are not evidence of relevant technical experience.
- Marketing Operations Lead and BDR Team Lead survived operations-management
  matching; those are adjacent/possible false positives, not verified matches.
- Broker Account Manager is only adjacent to customer success. Compliance
  managers may require seniority or expertise not tested by literal title input.
- Title phrase matching can miss aliases/plurals. Small selected boards and
  missing global APIs prevent claims about total market supply.
- Missing categories in this sample: IE support, IE operational fraud/trust,
  IE payment operations, UK remote support. Senior/technical skew matters.

## Dedupe and Freshness

Observed duplicate records: **0/69 (0%)** within first successful board payloads.
All 69 were created, so no cross-board merge was observed. This sample contains
different employers and is not a meaningful estimate of aggregator overlap.
Across time, all 69 IDs were retained and the second run was **100% unchanged**,
with zero new rows, zero updates and refreshed `last_seen_at`. No missing IDs
were observed. Unchanged repeats are not a duplicate flood.

Controlled offline cases exercised separately:

- Exact URL plus matching title/company/location across two providers: one job,
  multiple provenance rows, no candidate analysis.
- Same provider changes ID but retains exact identity: existing job reused.
- Same title/company but different URL, or tracking query changed: separate jobs.
- Same URL but conflicting title, company or location: separate jobs.
- Two equally strong legacy matches: a third observation stays separate.
- Reappearance refreshes provenance and clears archive. Age alone cannot archive.
- Missing-from-board needs repeated complete successful absences plus age;
  incomplete/failed/recent/active/personal/global-protected evidence blocks archive.

False separation is intentionally tolerated. The fixtures establish specific
conservative cases, not a universal guarantee against false merges.

## Scheduler Operations

Real scheduler with collected-job replays: four initial claims, three successful
sources and one isolated failure. Immediate repeat skipped all four as not due.
Success set next eligibility +6h; Plaid failure used +30m backoff. After the
simulated +8h, sources were claimable again and successful imports were unchanged.
Run history contains counters, safe failure categories and completion flags.

Offline regression additionally verified concurrent SQLite claim ownership,
stale claim recovery, fenced renewal/completion, lost-claim discard, failure
isolation, disabled/duplicate registry entries, global daily/employer cadence,
rate-limit backoff, incomplete coverage, shared subscriptions and JSON CLI output.
Global/employer coexistence and CLI use doubles, not live global-provider calls.

## Verification and Scope

- Focused coverage/scheduler/Source V2/connectors: **169 passed** (network blocked).
- Full suite: **1123 passed, 2 skipped in 56.66s** (socket/DNS blocked).
- `git diff --check`: passed; new artifacts also checked with `--no-index`.
- Added reproducible opt-in validation script, synthetic-profile/budget tests,
  conservative overlap tests, this report and sanitized JSON evidence.
- No production module, schema, UI, connector or scheduling policy changed.
- No commit or push.

Re-run only with explicit live authorization: `python -m scripts.validate_launch_coverage
--live --output docs/validation/launch_1e_evidence.json` (one command).
Each execution has its own cap; running it again performs another collection.
