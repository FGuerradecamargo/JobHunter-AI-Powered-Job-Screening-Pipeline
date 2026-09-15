# Launch 1C: public employer board connectors

## Contracts reviewed

Documentation reviewed on 2026-09-15; no live board queried. Synthetic fixtures
exercise these contracts, not captured employer/candidate data.

### Lever

[Official postings API](https://github.com/lever/postings-api)
documents HTTPS `GET /v0/postings/{SITE}?mode=json&skip=N&limit=N` on
`api.lever.co` or `api.eu.lever.co`. SITE is the board name, not a hostname.
The response is a list: `id` identifies a posting; `text` supplies its title;
`categories.location/allLocations` supply locations; `hostedUrl` is its public
page. Description fields have plain/HTML forms, with lists and additional
closing text. `workplaceType` distinguishes remote, onsite, hybrid and
unspecified. No reliable publication timestamp is documented in this public
field contract, so the adapter leaves `published_at` unknown.

### Ashby

[Official public posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
documents `GET https://api.ashbyhq.com/posting-api/job-board/{JOB_BOARD_NAME}`.
The case-sensitive board name is the hosted board's path segment. The response
contains `apiVersion` and `jobs`; this contract documents no pagination.
Each posting supplies title, location/secondaryLocations, plain/HTML description,
jobUrl, remote/workplace information and isListed. Unlisted entries are not for
board discovery. `publishedAt` means last publication, not necessarily original
creation. A separate posting `id` is not guaranteed by the documented schema.

## Adapter decisions

- Public company name comes only from the trusted companies registry. Neither
  adapter guesses it from the board key or reads candidate/watchlist data.
- Execution source identity remains `{vendor}:{company_job_sources.id}`, as
  required by Launch 1B. Returned IDs are `{execution}:{board}:{posting-id}`.
  Registry row IDs must remain stable. Recreating a registry row changes its
  execution namespace; Source V2's existing exact canonical matching remains
  authoritative. No fuzzy matching is added.
- Lever uses its ID and checks agreement with its hosted URL. Ashby consistently
  uses the posting path segment after the board in jobUrl, even if an undocumented
  `id` appears later. Tracking queries do not affect identity.
- Only vendor-hosted HTTP(S) job URLs with the correct board/posting path are
  accepted. Ports, credentials, traversal, whitespace and arbitrary hosts fail.
  Valid query/fragment components remain in the URL as Source V2 expects.
- Lever remote=true only for remote, false for onsite; hybrid/unspecified stay
  unknown in the boolean, with the original workplace text retained in raw_text.
  Ashby copies only an actual boolean isRemote. Optional unknowns are not invented.
- Plain descriptions are preferred; HTML fallback uses HTMLParser, drops script
  and style content, and retains text boundaries. Lever sections are included.
- `BoardJob` extends Job with an explicit optional UTC `published_at`. Ashby
  parses timezone-aware ISO values; invalid/naive dates remain unknown. Existing
  ingestion does not persist this field. No database migration or metadata blob.
- A malformed record is skipped and counted in the adapter's `skipped_records`;
  valid siblings survive. No raw payload/error is logged. Setup errors raise
  sanitized BoardError codes before queries; query/shape errors fail that feed.

## Fetch boundaries

The employer registry requests one whole-board query. Keyword/location filters
and noninitial pages are rejected to prevent accidentally incomplete coverage.
Lever uses results_per_page as an internal page size (maximum 100), not a board
result cap; it advances skip until a short/empty page. A repeated full page or
100-page ceiling fails the fetch instead of claiming complete coverage. Ashby
reads one full response and ignores the result-count hint.

HTTP uses fixed vendor-controlled HTTPS endpoint templates. Validated public
slugs cannot introduce a host, path separator, query or fragment. Lever defaults
to global; a registry careers_url on jobs.eu.lever.co selects only the fixed EU
template. Other careers URLs are never fetched. Redirects are refused entirely.
No dynamic DNS target, URL supplied by a posting, or user input is used for feed
requests. TLS verification remains on. Fresh sessions disable ambient proxy and
.netrc configuration; no credentials or shared global requests/session object.

Connect/read timeouts are 5/20 seconds. Safe GET retries have at most 3 attempts
for timeout/connection failures and 429/502/503/504. Backoff is bounded; numeric
Retry-After up to 5 seconds is honored. Longer/date hints defer to the scheduler.
Other HTTP failures, redirects, bad content type and malformed JSON fail without
retry. These are conservative client policies, not claimed vendor quotas.
Decoded HTTP bodies are bounded to 8 MiB, boards to 10,000 jobs and 20 MiB raw
text. Exceeding a limit fails the board, never silently truncates it.

## Wiring and Launch 1D

```python
from services.employer_provider_factories import employer_provider_factories
from services.employer_provider_registry import build_employer_provider_configs
from services.daily_ingestion_service import DailyIngestionService

# sources: trusted CompanyJobSource rows selected by the scheduler
configs = build_employer_provider_configs(sources, employer_provider_factories())
# Calling run performs network IO; do not execute in offline validation.
result = DailyIngestionService(providers=configs).run()
```

Factories remain lazy. Disabled/unsupported sources are skipped by the existing
bridge. DailyIngestionService is unchanged and isolates failing providers.
Source V2 persists global provenance and last_seen_at for observed jobs, with
no candidate ownership attached. A failed later page returns no partial board
to ingestion. Missing jobs are neither deleted nor closed by these connectors.

Launch 1D can schedule these factories without connector/schema redesign, but
must add scheduling cadence, per-source outcomes/coverage history and retry
policy. It must not treat a single absence, an incomplete/error fetch, skipped
records, or a long-unpolled source as proof of closure. Existing archive logic
requires explicit scheduling review. Offset pagination is not a vendor snapshot
guarantee; concurrent board edits can shift records. Duplicates are collapsed,
but closure requires additional evidence. Durable posted-date storage, custom
hosted job pages, pagination beyond the safety caps and public salary mapping
remain explicit future work. No scheduler activation or UI is added here.

## Changed files and validation

- `services/job_sources/board_http.py`: bounded HTTP and sanitized errors.
- `services/job_sources/employer_board.py`: shared parsing, URL checks, BoardJob.
- `services/job_sources/lever_source.py`: Lever global/EU adapter.
- `services/job_sources/ashby_source.py`: Ashby adapter.
- `services/employer_provider_factories.py`: trusted factory map.
- `tests/test_employer_board_connectors.py`: fake HTTP and SQLite integration.
- `docs/launch_1c_employer_connectors.md`: contract and operational notes.

Offline validation: connectors 92 passed; Launch 1A/1B 84 passed;
source/ingestion 40 passed; authentication/isolation 67 passed;
full suite 1078 passed, 2 skipped. Test processes blocked outbound sockets/DNS.
No AI or live API/feed requests were made. Only official documentation was
consulted through web research, separately from implementation validation.
