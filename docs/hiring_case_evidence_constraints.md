# Evidence constraints: source-backed and orthogonal

The existing uncommitted interpreter, reviewed calibration, adversarial fixtures and Career Journey
work are preserved. Frozen case facts and expectations are unchanged. No production UI integration,
provider calls, schema migration or production writes are introduced.

## Contract and authority

EvidenceRequirement is DEFENSIBLE (default) or DIRECT_REQUIRED. Requirement importance remains
CORE / IMPORTANT / NICE_TO_HAVE. Historical snapshots decode absent fields as DEFENSIBLE.
New fields round-trip through the existing JSON profile snapshot repository, without DDL.

The trusted hard layer marks explicit prior-ownership requirements and their need ID. Interpreted
needs must cite those specific hard facts, have EXPLICIT authority and bind the same need ID.
A generic ownership responsibility is insufficient. Invalid, implied, cross-need or missing refs
reject with a content-free code. Omitting a known explicit direct constraint also fails closed.
Both structured validation and the profile-to-engine adapter enforce the same validator.
No job-text pattern matching or automatic source extraction is added.

RequirementAssessment computes constraint_satisfied and constraint_reason_code from the normalized
evidence state plus EvidenceRequirement; callers cannot supply a forged satisfaction boolean.
TRANSFERABLE stays TRANSFERABLE when direct ownership is required. It is never promoted to PROVEN
or relabeled GAP simply to make the constraint fail.

## Strength and proof

- CORE + DIRECT_REQUIRED + TRANSFERABLE -> WEAK, not INELIGIBLE.
- IMPORTANT + DIRECT_REQUIRED + TRANSFERABLE -> VIABLE.
- NICE_TO_HAVE + DIRECT_REQUIRED + TRANSFERABLE does not automatically reduce STRONG.
- IMPORTANT + DEFENSIBLE + TRANSFERABLE preserves the reviewed HC15b behavior.
- PROVEN satisfies either requirement. Existing missing-evidence and confirmed-gap semantics remain.

Final quadrant classification is unchanged. HowToProve includes the requirement, satisfaction and
reason, and describes the direct-ownership limitation without scripted interview answers.
Adjacent experience does not generate an Add Evidence request. Missing evidence may still invite
an example. Confirmed GAP with an explicit direct requirement does not repeat an evidence request.
Legacy callers with default DEFENSIBLE retain their existing behavior.

## Preferences

OpportunityFact can carry conflicting_preference_refs from the trusted source layer: two or more
distinct, current, equally authoritative candidate preference sources, scoped to the candidate.
The relevant signal becomes UNKNOWN with uncertainty and a content-free conflict code. No newest,
most favorable or convenient preference is chosen. A resolved conflict requires a changed input
and signature; a prior result cannot be replayed. The existing Career Memory source projection has
no general equal-authority conflict resolver; this additive representation does not redesign it.

AV30 source projection explicitly maps its frozen contradiction to two preference refs; no text
matcher detects conflicts. Real-source conflict identification remains a future trusted interpretation
and user-confirmation responsibility. These flags are never accepted from provider output.

## Intentionally unresolved

At this slice's original completion, AV28 recency was deferred. The subsequent explicitly reviewed
Temporal Applicability Contract V1 now supplies that orthogonal contract and updates AV28 alone;
see temporal_applicability_v1.md. The new model does not introduce age thresholds or a prose parser.

AV05, AV06 and AV27 remain semantic-support failures. Valid IDs establish provenance, not relevance,
complete coverage or entitlement to reuse evidence for unrelated needs. A real structured interpreter
and independent evaluation are still needed; no keyword, regex, embedding or similarity workaround
is added. The offline cases are agent-authored proposals, not measured provider accuracy.

## Files in this hardening pass

- models/hiring_case.py: evidence requirement and derived constraint result, proof metadata.
- models/profile_interpretation.py: explicit source-bound job constraint fields.
- models/structured_interpretation.py: validation codes and preference conflict refs.
- services/job_evidence_constraints.py (new): shared source authority invariant.
- services/structured_interpretation_validation.py: constraint and conflict enforcement.
- services/profile_hiring_case_adapter.py: validated requirement propagation.
- services/hiring_case_engine.py: strength resolution and honest proof guidance.
- services/profile_snapshot_repository.py: additive legacy-safe JSON decoding.
- tests/hiring_case_adversarial_runner.py: explicit fact projection and constraint metrics.
- tests/test_hiring_case_evidence_constraints.py (new): second-order adversarial coverage.
- docs/hiring_case_adversarial_v1_report.md: regenerated observations, unchanged expectations.
- docs/activation_onboarding_todo.md (new): P0 onboarding specification only.
- docs/career_journey_todo.md: expanded product direction, no route rename.
- docs/hiring_case_evidence_constraints.md (new): this contract and limitations note.

The previous uncommitted files remain present. Neither frozen case file nor its freeze manifest
was edited in this pass. Source-signature and frozen-expectation tests continue to enforce that boundary.
