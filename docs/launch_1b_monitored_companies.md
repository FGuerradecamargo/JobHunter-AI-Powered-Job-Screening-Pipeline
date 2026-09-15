# Launch 1B: Monitored Companies and Employer Source Registry

## Audit and rollout

Before this slice, company identity was free text on Job.company. Source V2
normalized company text for conservative URL-based deduplication but had no company
entity. Profiles and career objectives did not hold explicit company watchlists.
Job provenance distinguished global sources from user-owned sources.

After this slice:
candidate -> private monitored-company relationship -> shared company
-> trusted employer source rows -> ProviderConfig -> Source V2 ingestion.

Existing jobs remain text-backed. No historical company strings, candidate profiles,
career objectives, analysis records or job provenance are rewritten. Company
monitoring is an explicit interest, not a career objective.

## Schema

Both initialize_sqlite_database and initialize_postgres_database call
create_company_registry_schema after the base candidates/users tables exist.

- companies: id, canonical_name, normalized_name (unique), optional domain and
  careers_url, created_at, updated_at.
- candidate_monitored_companies: candidate_id + company_id primary key, active
  (0/1), created_at, updated_at. Both references have cascading deletes.
- company_job_sources: id, company_id, source_type, source_key, optional careers_url,
  enabled (0/1), created_at, updated_at. Unique company_id/source_type/source_key.

All three PostgreSQL tables have RLS enabled under the existing server-only
allowlist. No client policies or grants are added. Shared means shared through the
trusted backend, not anonymously readable or writable through PostgREST.
The backend database role must retain its existing server-side access model.

Schema creation is additive and idempotent and uses the existing bootstrap
transaction/serialization. SQLite and PostgreSQL use the same DDL and integer flags.
Repository SQL uses ?; PostgresConnectionAdapter translates to %s.

## Identity and validation

company_name applies NFC Unicode normalization, trims and collapses whitespace,
normalizes curly apostrophes to straight apostrophes, then casefolds the lookup key.
It does not remove legal suffixes, hyphens, accents or other meaningful punctuation.
Meta and Meta Platforms Ireland remain distinct, as do Bank of Ireland and
Bank of Ireland UK. No abbreviation guessing, parent/subsidiary matching or AI exists.

A normalized name identifies a company for this rollout. A conflicting supplied
domain for an existing known domain is rejected for explicit review. Exact-name
homonyms cannot yet coexist; this is safer than silently treating conflicting
domains as one company. Domain is optional and no discovery/verification is done.

get_or_create_company preserves an existing record and its original timestamps
and metadata. Supplying optional metadata again does not overwrite an existing
company. Enrichment and explicit alias/homonym resolution are future admin work.

Careers URLs accept HTTP(S) public-style URLs without embedded credentials, ports,
query strings or fragments. Source type/key accept bounded public identifier syntax.
No API key, token or arbitrary metadata argument/column exists. Operators must supply
public board keys, never credentials. These validators are not an SSRF policy;
future connectors must construct/allowlist their own vendor endpoints and validate
redirects before making requests.

## Ownership and explicit actions

MonitoredCompanyRepository requires the server's UserContext. Every list/add/stop
checks the active user's persisted candidate association and the authenticated
user's persisted existence/role. Passing another candidate_id fails.

Cross-user context additionally requires:
- persisted admin role;
- AdminAccessSession authorization for precisely the active target user.

The repository does not create an admin grant. Runtime callers obtain UserContext
from the existing authenticated/active-user boundary and pass the existing admin
session. Objects supplied directly by a client must never be used as authentication.

monitor_company is the explicit mutation. Duplicate adds reactivate the same row
without replacing its creation timestamp. stop_monitoring_company is an idempotent
deactivation; listings include active relationships only. Stale candidate associations,
forged in-memory roles and missing/wrong-target grants are rejected.

Global Company and CompanyJobSource objects expose no candidate IDs or watchlists.
CompanySourceRepository is a trusted backend management interface, not a public
candidate write API. No UI or external endpoint was added.

CompanyRepository.find_company is the deterministic lookup/suggestion boundary.
A suggestion or a shared company lookup never creates a monitored relationship.
No browsing-based inference, AI suggestions, entitlements or billing are introduced.

## Launch 1C integration

services/employer_provider_registry.py provides:
build_employer_provider_configs(sources, factories) -> tuple[ProviderConfig, ...].

1. In the authenticated candidate path, list_monitored_companies(candidate_id)
   supplies that candidate's explicit active choices.
2. Load shared sources with CompanySourceRepository.list_company_sources(company.id).
3. Pass source rows to build_employer_provider_configs with a trusted factory map,
   e.g. lever -> factory(row), ashby -> factory(row).
4. Pass the returned configs (optionally alongside default_providers()) into
   DailyIngestionService(providers=configs).

The conversion is lazy: no factory runs and no fetch occurs during configuration.
Disabled or unsupported source types are skipped. Duplicate rows are deduplicated
by execution name. Multiple companies/boards can coexist in one run.

Each future adapter must expose source_type = employer_run_name(row), currently
<connector_type>:<source_row_id>. This is a stable per-feed key, required because
Source V2 identifies provider results by source_type. It must implement the existing
search signature and return Job values with stable board-scoped IDs. It can use
<execution_name>:<external_job_id> as the ID; source_key identifies the public board.
The feed query plan contains one empty query, so full-board connectors can ignore
keywords. Private candidate/company-selection metadata must not be copied to Job
or shared source provenance.

Changing a public board key creates a different source identity; disable the old
entry explicitly. A future background scheduler can deduplicate eligible companies
server-side; exposing private subscribers is unnecessary. This slice does not add
a background watchlist-enumeration endpoint or scheduler.

Unsupported future source types may be stored. An enabled unsupported row is still
not executable until an allowlisted factory is installed. Company monitoring works
with zero sources.

## Verification and limits

Tests use temporary SQLite and a translating PostgreSQL driver double for the
repository paths, plus PostgreSQL DDL/RLS assertions. No live PostgreSQL or ATS
server is exercised. Tests block network operations and use fake ingestion clients.

Launch 1C can add Lever/Ashby connectors without changing these tables or
DailyIngestionService. Remaining work includes real vendor adapters, endpoint safety,
pagination/rate limits, scheduling, board verification, and candidate-facing UI.
Source V2's alias-map and concurrent deduplication limitations from Launch 1A remain.
Jobs are not yet linked to companies by company_id; no automatic name backfill is
performed. More granular employer provenance can be added when demonstrated by
connector requirements, without making private watchlists global.
