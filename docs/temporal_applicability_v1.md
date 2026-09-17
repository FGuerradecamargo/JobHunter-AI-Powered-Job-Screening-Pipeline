# Temporal Applicability Contract V1

## Reviewed AV28 change

The user explicitly reviewed AV28: old procedure experience is real, relevant TRANSFERABLE evidence
for the materially changed current procedure. Expected temporal applicability is NOT_SATISFIED,
strength VIABLE, value HIGH, classification WORTH_A_TRY. It is neither missing evidence nor a gap.

Only AV28's expected evidence state/rationale and its controlled semantic reply changed under this
review. The reply now encodes the reviewed TRANSFERABLE relationship; the temporal resolver does NOT
derive that semantic assessment. Tests separately prove historical PROVEN can remain PROVEN.
The previous freeze digest is retained in hiring_case_review_freeze.json and the other 31 cases
have a separate unchanged-content digest. The reviewed original 40 cases are unchanged.

AV28 source projection uses the explicit company procedure requirement rather than the old generic
need label. Symbolic fixture version IDs current-procedure / obsolete-procedure express the supplied
material change; they are not invented regulatory version numbers or calendar dates.

## Contract

- TemporalRequirement: NOT_REQUIRED (default), CURRENT_REQUIRED.
- TemporalApplicability: SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_APPLICABLE.
- Hard job facts bind temporal_need_id, required_version, superseded_versions and/or material_change_on.
- Job interpretations cite explicit temporal_requirement_refs for the same need, with EXPLICIT authority.
- Candidate source metadata binds evidence ref, need ID, temporal_version and/or performed_on.

performed_on means the date of the evidenced practice, not a database insertion or CV upload date.
These are trusted source facts, never fields invented by a provider or taken from checkpoint prose.
Registry authority and candidate scope checks apply before temporal evaluation. The engine adapter
recomputes applicability from these metadata, instead of trusting a returned satisfaction claim.

## Conservative resolution

No temporal requirement means NOT_APPLICABLE and no temporal penalty, however old the evidence.
An explicit matching current version establishes SATISFIED unless contradictory pre-change timing
is supplied. An explicitly superseded version or practice predating an explicit material change
establishes NOT_SATISFIED. Unknown dates/versions or contradictory facts retain UNKNOWN.
A practice date after a procedure change alone does not establish use of the new procedure.
Historical plus current refresh evidence can satisfy the requirement while preserving both sources.
There is no wall-clock dependency, generic age threshold, keyword, regex or embedding matcher.

Job constraints cannot be silently omitted, invented from strongly implied wording, or linked to
another need. Dates must be ISO calendar dates; malformed metadata fails with content-free codes.
Unrecognized version IDs are uncertain, not automatically obsolete. All explicit temporal constraints
on a need must be satisfied; one explicitly unsatisfied constraint suffices to retain NOT_SATISFIED.

## Product behavior

CORE or IMPORTANT temporal mismatch limits an otherwise strong case to VIABLE. Existing explicit
GAP, direct-evidence and scope rules still apply independently. NICE_TO_HAVE mismatch alone does not
destroy STRONG. UNKNOWN lowers semantic-link confidence and exposes uncertainty without automatically
changing evidence state, opportunity valence, or creating INELIGIBLE.

HowToProve retains historical/adjacent experience and identifies the need to demonstrate current
procedure knowledge; it cannot imply that historical work proves current proficiency. New structured
fields allow future Career Journey to distinguish REFRESH from LEARN FROM ZERO. No UI changes.

## Compatibility and limits

Additive fields default to NOT_REQUIRED / NOT_APPLICABLE. Old profile JSON decodes safely; new fields
round-trip without a schema migration. All prior uncommitted work remains present. No provider calls,
network, production DB access, commit or push are part of this slice.

Trusted temporal metadata still needs accurate real-source acquisition and user review before future
production integration. Semantic relevance remains a separate interpreter responsibility: the remaining
adversarial support failures are not solved by temporal rules or proven by these synthetic fixtures.
