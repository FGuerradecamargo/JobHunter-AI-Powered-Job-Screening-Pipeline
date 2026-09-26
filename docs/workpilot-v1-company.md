# Block 8: public CompanyProfile

CompanyProfile is global company context, not a candidate relationship. Existing
companies registry IDs are reused via a foreign key. No automatic research,
provider client, candidate import, or interviewer research is added.

The deterministic builder accepts explicitly company-scoped public professional
sources. Known private provenance is rejected even with public=True. The source
classification is an ingestion trust boundary, not proof that arbitrary caller
text came from the web; integration must resolve independently public evidence.

Every nonempty context value requires a CompanyClaim referencing a source and
an exact supporting excerpt in its summary. Claims remain source_reported,
including marketing/culture language. They are not verified facts. Missing
fields remain empty/unknown. No personal-life interviewer fields exist.

Company snapshots preserve sources, claims, uncertainties and version history.
Signatures cover sources plus the grounded projection. Identical builds reuse
the current snapshot. A changed source/projection creates a new version;
conflicting writers must reload rather than overwrite history. The repository
does not initialize schema on reads/writes.

Migration: additive company_profile_snapshots table in the existing explicit
initialization path, compatible with SQLite/PostgreSQL, with server-only RLS and
direct-role revocation on PostgreSQL. No existing company/candidate/job data is
rewritten. Real PostgreSQL deployment and public-source integration remain E2E
work; no production database or network was used for this implementation.
