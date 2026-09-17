# Offline structured interpreter v1

Shadow-only, provider-neutral validation boundary. Production remains legacy-authoritative.
No provider client, repository writes, UI integration, or automatic evidence updates are added.

## Flow

Trusted source projection and registry -> exact fixture lookup -> strict decoded schema ->
source/authority validation -> request-bound envelope -> existing profile adapter -> deterministic engine.

The four operations are BUILD_CANDIDATE_PROFILE, BUILD_JOB_PROFILE, ANALYZE_HIRING_CASE,
and INTERPRET_OPPORTUNITY_VALUE. Fixtures supply hypothetical provider replies, never final labels.
Missing fixtures return UNAVAILABLE with no payload. The input digest includes operation, schema,
source projection, registry, profile versions, checkpoint and opportunity facts. Calibration facts
are additionally pinned in a manifest so changing facts cannot silently reuse authored responses.

## Trust boundaries

The caller must build the registry from candidate-scoped source records, not model output.
Career Memory signatures come from the trusted source layer. SHA-256 lookup signatures bind content;
they are not authentication or cryptographic attestation of source truth. No production loader is added.

Candidate evidence and Career Memory sources are distinct from job hard facts and checkpoints.
Only usable experience/update sources can support proof. Confirmed absence is supplied by the source
registry, not inferred from checkpoint prose or generated profile gap labels. Unsupported GAP becomes
EVIDENCE_MISSING. Transferable profile capabilities cannot be promoted to direct proof by a link.

Checkpoints are derived, non-evidentiary input. They may support version-delta descriptions only.
Checkpoint/derived refs, including mislabeled checkpoint source types, fail the central firewall.
Question hints remain non-authoritative output and cannot update source records or promote evidence.

Job needs require job hard-fact refs. Only explicit needs backed by a hard-layer blocker may block.
Unknown job needs remain uncertain. Opportunity signals cover nine dimensions, retaining fact state,
sentiment, authority, supporting refs and uncertainty. Unknown compensation cannot become negative.
Known interpreted signals must cite the complete dimension-specific supporting reference set.

The boundary revalidates accepted envelopes before conversion; stale signatures and mismatched profile
pairs cannot enter through it. Result metadata has operation, schema/interpreter versions, input signature,
time, validation status and issue codes with authoritative=false. Results are in-memory; no prompt,
chain-of-thought or private content is persisted by these modules. Logs contain codes and counts only.

## Limits and next step

Valid references establish provenance, not semantic entailment. A hypothetical provider could cite a
real evidence record while misrepresenting its meaning; this structural validator cannot detect every
such lie. The 40 synthetic cases remain agent-authored, pending human review. Agreement is not measured
provider accuracy. Review the fixtures and disagreement cases, then add held-out adversarial examples
before implementing a real provider. Keep the engine and production path unchanged until that review.

## Reviewed source repair distinction

The three product decisions HC12b/HC15b/HC20b are now reviewed; all other original judgments remain
pending. See the regenerated calibration report and separate frozen adversarial-v1 report.

`source_repair_need_ids` is supplied only by trusted source-layer detection of existing orphan records,
never by the interpreter. For unresolved proof it normalizes the link to EVIDENCE_MISSING with
SOURCE_REFERENCE_UNAVAILABLE, needs_source_repair=true and needs_evidence=false. An interpreter
cannot grant itself this flag. Invalid supplied refs still reject; valid repaired refs may later prove
the same capability. The envelope preserves these flags for future UI use; legacy UI and generic
engine proof prompts are intentionally not wired to this shadow-only metadata in this slice.
