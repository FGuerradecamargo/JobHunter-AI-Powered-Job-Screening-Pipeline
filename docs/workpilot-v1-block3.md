# Block 3: HiringCase relationship authority

Vacancy facts describe requirements, not candidate incompatibility. A legacy
`hard_blocker` flag on a Job never establishes ineligibility by itself.
`AuthoritativeHiringCaseService` checks identity/signature before interpretation,
then delegates relationship validation and classification to the existing adapter
and HiringCase engine. Profile versions/signatures remain attached to the result.

For explicit REQUIRED + NON_SUBSTITUTABLE finite facts, the adapter resolves the
candidate's source-backed structured state independently of AI links:

- `work_authorization`: value is an exact jurisdiction. Authorized/compatible/active
  establishes support; denied/unauthorized/incompatible establishes contradiction
  only with confirmed-complete coverage. Other statuses remain unknown.
- `language`: value is an exact language name. Presence establishes language
  possession, not an unrecorded proficiency level.
- `licence`: value is an exact licence name. Active supports; expired contradicts
  with confirmed-complete coverage; pending/unknown does not establish absence.
- A missing item supports absence only with confirmed-complete coverage and a
  source-backed candidate snapshot. Partial/unknown coverage never rejects.
- Conflicting records remain uncertain. No substring, prose or inferred synonym
  matching is used to manufacture incompatibility.
- Explicit relocation/night-work requirements can conflict with source-backed
  `CONSTRAINT` preferences whose value is `not_allowed`, with complete coverage.

The existing proof/add-evidence contracts retain unresolved candidate evidence.
No new AI calls, source ingestion, schema migration or production UI cutover are
part of this block. Existing stored HiringCases need not have provenance fields;
their dataclass defaults preserve compatibility.

## Migration classification

- MERGE: profile adapter and HiringCase engine remain the single evaluation path.
- REPLACE: unconditional Job-to-relationship hard-blocker conversion is removed.
- KEEP: legacy/shadow entrypoints remain for regression and later runtime cutover;
  this commit does not claim the Streamlit production path has been switched.
- DELETE: no unrelated legacy components removed.

Frozen calibration judgments are unchanged. Their fixtures now project confirmed
candidate contradictions separately from the vacancy requirement rather than
encoding both as a global job flag.
