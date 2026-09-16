# Sprint 13B: Tailored CV failure diagnostics

## Observed defect and evidence

`pages/1_Opportunities.py` calls the production preparation factory only for an
explicit action. `handle_prepare_application_action` stores the result in the
Streamlit session. `prepared_application_error_message` previously mapped EVERY
`generation_failed` result to "The generated material did not pass validation."
This also masked client errors, claim acquisition errors and concurrent work.
It cannot establish that either reported production attempt reached Truth Guard.

The forced READ ONLY production inspection on 2026-09-16 found zero rows in
`candidate_preparation_generation_claims`. Schema inspection for generation,
prepared and tailored tables found only that claim table. Its columns contain
scope, claim token and timestamps, not validation history. No private row data
was read. No mutations were performed.

The code does not persist CV generation diagnostics. Failed session results retain
the final error code and issue list, but not attempt count. The generator result
has attempt count and repair signature; these are not retained by preparation.
The OpenAI adapter returns output text only, discarding response model/usage
metadata. Job-analysis runs are not CV generation runs. The production Streamlit
session and deployment logs were not accessible in this investigation.

Consequently the exact historical rejection, whether repair ran, and whether
both attempts failed at the same stage are UNKNOWN. Repeated generic UI text is
not evidence of the same internal failure. Zero remaining claims does not prove
which attempts ran or succeeded.

## Failure path and gates

Preparation builds the scoped ApplicationContract and ApplicationContext, acquires
a lease, and calls TailoredCVGenerationService. Its request builder selects evidence
and builds a JSON-oriented prompt. TailoredCVGeneratorAdapter delegates to
OpenAIClient.generate. The returned output text passes through
parse_tailored_cv_response and validate_tailored_cv_draft. Only a validated draft
can become a prepared result. The preparation service rechecks returned CV scope.

| Gate | Internal code/type | Repair |
| --- | --- | --- |
| Missing IDs, missing analysis, permission/scope mismatch, ineligible contract, contract/context construction | invalid_request, analysis_not_found, scope_mismatch, ineligible_application, contract_failed, context_failed | No generation |
| Claim unavailable/acquire failure | generation_in_progress, generation_claim_failed | No generation |
| Ineligible context or empty selected evidence | ineligible_application, no_selected_evidence | No generation |
| Client raises | generator_client_error | No |
| Invalid JSON, non-object response | TailoredCVParseError -> invalid_generator_output | No |
| Missing/wrong-type strings, statement objects, string-reference lists, section/experience/bullet lists; unsupported schema version | TailoredCVParseError -> invalid_generator_output | No |
| Candidate, job, context signature mismatch | candidate_mismatch, job_mismatch, context_signature_mismatch | No |
| Empty statement or invalid claim type | empty_statement, invalid_claim_type | Once |
| Missing/unknown reference | missing_evidence_ref, unknown_evidence_ref | Once |
| Experience bullet references wrong source ID or non-experience evidence | experience_source_mismatch | Once |
| Authority cannot support claim | insufficient_evidence_authority, developing_evidence_overclaim, transferable_evidence_overclaim | Once |
| Protected structural gap terms claimed without matching professional fact | protected_gap_conflict | Once |
| Repair client/parser failure | repair_client_error, invalid_repair_output | No further repair |
| Repair Truth Guard failure | repair_exhausted plus final issue codes | No further repair |
| Unexpected generation exception | generation_service_error | No further repair |
| Successful result lacks CV or has incorrect scope | missing_validated_cv, validated_cv_scope_mismatch | No |

All Truth Guard issues must be repairable for a repair to run. Setting the repair
limit to zero disables it; constructor permits only zero or one. Nonrepairable
initial issues yield truth_guard_rejected. Skills, headline, summary, additional
information and experience bullets all use statement validation.

There is NO separate date/contact validation in this schema. Empty section lists
and empty experience bullet lists are accepted. Company and role must be strings,
but their content is not independently checked against source facts. There is no
general semantic entailment validator for every responsibility, technology or
metric: authority/reference checks and protected-gap term matching are narrower.
These limitations are not changed by this diagnostic slice.

The prompt names tailored-cv-v1 but does not include a complete output schema.
This is a possible structural-failure risk, NOT a diagnosis of the two attempts.
No prompt or validation policy was changed without evidence of the actual failure.

## Changes and safe operation

UI now maps static, allowlisted issue codes to safe explanations and distinguishes
client/claim failures from validation failures. It never displays issue messages,
locations, references, generated text or exception strings.

Content-free JSON logging records stage, error code, validation codes, issue
count and repair_attempted. The initial Truth Guard failure is logged before repair
(repair_attempted=false at that point), followed by the terminal repair result
(true). Successful repairs are therefore visible too. Parse/client failures have
zero Truth Guard issues. Unknown diagnostic codes are reduced to fixed markers.
No CV, prompt, identity, evidence reference, context signature, token or secret is
logged. This adds no durable database history or schema change.

The existing persisted lease is scoped to candidate/job/context signature, expires
after 900 seconds, and is released in finally using its owner token. A release
failure can leave a lease until expiration, not a permanent block. The existing
TTL can also expire during unusually long in-flight work; this is a bounded lease,
not a guarantee beyond its lifetime. The generation service makes at most two
client invocations; provider SDK transport retries are separate and unchanged.

Failed UI results do not suppress another explicit attempt. Successful results
are reused within the same session. The regression test runs failed generation +
failed repair through preparation and a real isolated SQLite claim repository,
checks claim deletion, then verifies successful retry and cached reuse.

## Next production diagnostic

Deploy these changes first. With separate user approval, one controlled generation
would now be useful to capture the actual failure code/stage. Do not clear caches
or repeatedly generate as a diagnostic substitute. For support, share only the
content-free tailored_cv_validation JSON records and the safe UI reason, never
full exception traces, prompts or CV text. This task performed no live generation.
