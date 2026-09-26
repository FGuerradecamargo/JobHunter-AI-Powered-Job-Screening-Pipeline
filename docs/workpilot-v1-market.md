# WorkPilot V1 Market boundary

## Block 6

`MarketJobObservation -> MarketProfile` is the official global market contract.
It has no candidate ownership or candidate-derived recommendations. All calls
are offline and deterministic; this block makes no provider or AI calls.

`public_market_observation` accepts independently public provider facts only,
with a null user scope. It does not read shared `jobs` descriptions: a public
source row alone cannot prove that a legacy shared description was public.
Private Gmail/manual/import facts must not be relabelled public. Future source
integration must pass the public provider projection itself, not a mixture of
private and public payloads. The reserved observation-authority branch remains
unmerged. No production ingestion or UI cutover is performed by this block.

Identity precedence is exact company requisition, public URL (known tracking
parameters removed, identity query parameters retained), namespaced source ID,
then company/title/location/context fingerprint. Callers should supply the
strongest available identity consistently. No fuzzy merge or company/title-only
fallback exists. Cross-provider records without a common exact identity remain
separate rather than being guessed to be duplicates.

Repeated exact identities count once. All public evidence contributes to the
signature, independent of input order. Conflicting scalar facts become unknown;
grounded capabilities/tools are collected. Frequencies describe this observed
sample, not the entire labour market. Small/empty samples retain uncertainty.
Salary coverage counts explicit compensation observations only, not market pay.
`time_window` is an inclusive timezone-aware ISO `start/end` interval; empty
means all observations up to `created_at`. Future observations are excluded.

The explicit additive schema addition is `market_profile_snapshots`, created by
the existing database initialization migration path. No existing rows/tables
are changed. SQLite and PostgreSQL share the DDL; PostgreSQL applies the same
server-only access restrictions as other profile snapshots. Repository reads
and writes do not run bootstrap or migrations. Snapshots are immutable; competing
writers must reload after a version conflict. Historical versions stay available.

## Transitional paths

- KEEP temporarily: CurrentMarketPosition, market_position_service,
  current_market_position_service and existing career-intelligence UI.
- REPLACE authority: candidate-derived evidence is not a global MarketProfile.
- MERGE later: UI/integration onto CandidateProfile x MarketProfile in Block 7
  and subsequent verified integration. Do not delete the legacy UI before then.

Real PostgreSQL migration and provider/browser integration remain E2E checks;
offline tests are not evidence that production has been migrated or switched.
