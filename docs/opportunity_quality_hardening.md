# Opportunity Quality and Test Data Isolation

Baseline: `f346186`, branch `feature/postgres-migration`, 2026-09-16.
Offline investigation only. No production database access or changes, external
provider, Gmail or LLM calls. No ranking thresholds changed. No commit/push.

## Test Contamination: Confirmed Risk, Incident Origin Unverified

The reported `Fraud Operations Analyst - Postgres Test Co` is absent from the
checked-out code and the Git history string search. Local `data/jobhunter.db`
was inspected using SQLite `mode=ro`: zero jobs, zero candidate analyses and
zero suspect rows. No private content or candidate IDs were printed.

Consequently, the exact creator, production job ID, candidate association,
source and analysis provenance **cannot be established from available data**.
There is no basis to assert a specific seed/test created this exact row.

Confirmed defect: there was no suite-wide database isolation. `database.py`
loads dotenv and chooses PostgreSQL whenever `DATABASE_URL` is set, otherwise
the persistent `data/jobhunter.db`. For example,
`tests/test_user_and_gmail_repositories.py` initializes and writes through that
connection without a temporary-DB fixture. Two PostgreSQL schema tests likewise
operate on the ambient configured database. This permits test artifacts/schema
writes in a shared runtime database when pytest is run with production config.

Other inspected entry points are manual scripts, not automatic production seeds:
`create_felipe_candidate.py`, `sync_database.py`, and
`migrate_candidate_job_analyses.py`. The last copies legacy job analyses to a
hardcoded candidate and could propagate contaminated legacy analysis if invoked
against a shared DB. Its execution in this incident is unverified. No literal
company-name exclusion or guessed synthetic-data classification was added.

Expected incident path, with unverified steps explicitly distinguished:

1. Creation/import into `jobs`: creator/source unknown for the reported record.
2. `job_sources`: shared global provenance permits discovery; personal provenance
   is scoped in discovery. Actual suspect provenance is unknown.
3. `candidate_job_analyses`: per-candidate status/recommendation/analysis JSON and
   active opportunity state determine visibility. Actual production row unknown.
4. Opportunities resolves authenticated user through active-user authorization,
   takes that active user's candidate ID, then calls `list_candidate_jobs`.
5. That query joins jobs and analyses with explicit candidate/status predicates;
   active analyses supply the displayed category. No company-name safety check
   exists, nor should one substitute for environment isolation.

No missing candidate predicate was found on this page query. Sharing a public
job is intentional; sharing another candidate's analysis is not. Regression
tests verify two candidates get different analysis results for the same public
job, while an unrelated candidate gets none. Existing normal/admin active-user
authorization tests remain part of regression. These findings do not prove that
every repository path or the actual production incident is isolated correctly.

## Isolation Fix

`tests/conftest.py` clears the database URL before test-module imports (so dotenv
does not restore it), assigns collection-time work a temporary SQLite path, then
gives each test its own initialized temporary DB. Actual PostgreSQL pool access
is rejected in the offline suite. Existing schema/adapter doubles remain usable;
ambient live-Postgres tests skip rather than using deployment credentials.

This protects jobs, analyses and other tables, including tests which forgot to
provide their own database fixture. It does not retroactively remove shared DB
contamination or isolate arbitrary manual seed scripts outside pytest.

## Safe Production Follow-up (Not Executed)

Release remains blocked on identifying/quarantining the actual contaminated row.
An authorized operator should use a read-only production session first:

- Locate exact job IDs by the reported title/company; inspect provenance,
  creation/update times and all candidate relations. Do not assume a name match
  alone authorizes deletion.
- Trace `candidate_job_analyses`, `candidate_job_analysis_runs`, `job_sources`,
  shared analysis/profile records and any prepared/interview/outcome dependencies.
  Compare timestamps with test/seed execution history. Inspect CV types/lengths,
  not private CV text in logs.
- Confirm which IDs and analysis runs are synthetic and whether a legitimate job
  has a synthetic analysis. Obtain explicit cleanup approval and a backup/export
  of the affected rows and foreign-key dependencies.
- In one reviewed transaction, remove **only confirmed synthetic records and
  their audited dependents** by exact bound IDs. For a legitimate job with a
  synthetic analysis, preserve the job and clean only affected candidate analysis
  projections/history. Verify row counts before COMMIT; otherwise ROLLBACK.
- Re-query affected candidates and the shared discovery pool; ensure no synthetic
  analysis history remains, and legitimate users/jobs are unchanged.

Do not run a wildcard company-name DELETE. Setting only `jobs.archived_at` is
not sufficient: the current active-opportunity query does not filter that field.
This report intentionally does not invent IDs or execute cleanup.

## Historical CV Rendering

Confirmed code defect: the page iterated `key_skills`, experience bullets and
additional information assuming lists. A string at one of those fields is
iterated by character; skills were emitted as `- {character}`, including marker
characters. Structured or malformed values could also leak serialization or
raise exceptions. Empty sections were checked before meaningful normalization.
Local history was empty, so this is a reproducible failure mechanism, not proof
of the exact production record shape.

`historical_cv_presenter.py` now normalizes dictionary or JSON-encoded CVs,
newline/string/JSON-array/list fields and singleton experience dictionaries.
Empty markers, nontext list entries and malformed structured values are omitted.
The existing page renders plain text instead of executing stored Markdown and
passes the same normalized representation to both existing exporters. Empty CVs
produce no expander. Valid legacy content remains supported; unsupported scalar
CV formats are omitted rather than guessed. Stored records are not rewritten.
This normalization is display-only, not Truth Guard validation or new generation.

## Analyst Findings

The direction matcher removes generic words including `analyst` and `operations`.
With Launch 1F's target of only `analyst`, the direction-token set becomes empty;
the loop skips its substring fallback. Business/PMO/contract titles therefore
fail even though they look like analysts. Specific `Business Analyst`, fraud and
risk-operation directions pass the existing rules in fixtures; mechanical and
investment analyst counterexamples remain rejected for that direction.

The retained 1F evidence includes only five of seven rejected titles. No network
recollection or private candidate profile was used. Individual classifications:

| Observed example | Classification | Why |
| --- | --- | --- |
| Contract Analyst II | C: ambiguous | Contract/legal/commercial domain and intended candidate path unspecified |
| Business Analyst - Trade Finance / Contingent Liabilities | C: ambiguous | Business path plausible; trade-finance evidence/intent unspecified |
| Senior Business Data Analyst - Transact system | C: ambiguous | Seniority, systems and data capability requirements unknown |
| Techno Functional Business Analyst | C: ambiguous | Technical/functional requirements not established |
| PMO Analyst | C: ambiguous | Plausible project/business adjacency, but target path unspecified |
| Rejected analyst 6 (title not retained) | C: insufficient evidence | Cannot reconstruct identity or requirements |
| Rejected analyst 7 (title not retained) | C: insufficient evidence | Cannot reconstruct identity or requirements |

No individual A (proven fit-direction false negative) or B (proven correct
rejection) can be established from the generic synthetic profile and retained
evidence alone. The generic-token rejection mechanism is confirmed, not final
candidate suitability. No production analyst rule was changed simply to admit
all analysts. Needed next: concrete intended/bridge families and the seven job
profiles, then domain-specific positive/negative regression cases. Existing
unconditional compatible-region rules also warrant later candidate-aware review.

## Potential Diagnostics

Observed user report: 1 Best Match, 15 Potential, 3 Competitive, total 19.
If the reported Best Match is the only contaminated result, arithmetic after
removing it is **0 / 15 / 3, total 18**. This is not a production remeasurement;
safe local data is empty and no cleanup was performed.

The page uses persisted `analysis.bucket` or `analysis.recommendation`; the
current batch path copies the parsed model recommendation to bucket. It does
not numerically recompute category from current fit/growth. The older
`classify_job_bucket` function is not the active batch category decision.

The prompt defines Potential as plausible competitiveness with important gaps,
and explicitly says growth/interest alone is insufficient. Competitive is the
UI label for `good_opportunity`, meaning competitiveness with trade-offs.
Parser diagnostics with fake responses confirm that Potential at fit/growth
30/95, 65/40 and 85/80 all remain Potential: it validates score ranges and enums,
not numeric consistency or category semantics. These are illustrative fixtures,
not inferred scores of the 15 real rows.

Conclusion: a broad semantic label by design, with limited semantic validation;
no demonstrated numeric-threshold defect or growth-based promotion in code.
The actual sample's fit evidence/gaps/trade-offs are needed to decide whether
its distribution is legitimate or model inconsistency. No thresholds or labels
were changed to improve the histogram.

## Validation and Remaining Blockers

Network disabled for all tests. Focused regression: **208 passed in 22.16s**.
Final full suite: **1154 passed, 2 skipped in 59.32s**.
`git diff --check` passed; new files also checked with `--no-index` (only
expected LF/CRLF warnings). No production UI smoke test was performed.

Files changed: `tests/conftest.py`, `tests/test_opportunity_quality_hardening.py`,
`services/historical_cv_presenter.py`, `pages/1_Opportunities.py`, and this report.

- P1 unresolved: production contamination origin, scope and approved cleanup.
- P1 unresolved: actual historical CV shape and deployed rendering smoke check.
- Analyst/category quality requires the missing direction/evidence context;
  synthetic score distributions do not establish launch quality.
- No broader cross-user leak was demonstrated on the inspected opportunity path;
  test-environment contamination was a broader confirmed risk and is now guarded.
