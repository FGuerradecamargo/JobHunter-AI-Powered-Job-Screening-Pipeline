# Block 10: Apply/CV boundary

V1ApplyFlow checks CandidateProfile / JobProfile / HiringCase IDs, versions and
signatures against an authorized ApplicationContext before invoking the existing
preparation service. Inject that service with its existing generation-claim and
repair controls; no new provider or generator implementation is introduced.

The existing Truth Guard is reused with strict text grounding enabled for V1.
Its legacy default remains compatible. Strict mode requires source-supported
statements and source employer/role metadata; a valid evidence ID alone does
not authorize invented text. This deterministic gate conservatively accepts
source wording, reordering, case/spacing and terminal-period changes. It does
not certify arbitrary semantic paraphrases. Such wording is flagged for review,
not silently repaired or accepted. Broader defensible paraphrase validation
remains an explicit future integration decision, not an assumed capability.

Manual edits are deep-copied documents and never mutate CandidateProfile. Their
original text is returned with issues even when rejected. The V1 export method
runs the same guard again immediately before calling the existing DOCX exporter.
The old exporter remains a compatibility API, not a V1 validation entry point.

ATS coverage is informational with matched, missing_with_evidence, and
missing_without_evidence categories. It never adds a skill. Four progress labels
are emitted as workflow callbacks; they are not candidate evidence.

Ready-to-apply persists only on an in-review candidate/job relationship. Opening
the validated HTTP(S) company URL returns a link and writes nothing. Only an
explicit boolean confirmation calls mark_applied; repeats stay idempotent.
No application is submitted by WorkPilot.

The official orchestration contract is tested offline. Production UI wiring to
V1 profiles, source metadata availability, live generation and browser E2E are
still pending. No live calls or production migration were performed here.
