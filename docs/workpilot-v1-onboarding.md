# Durable company interviews (Block 4)

`candidate_work_experiences.onboarding_status` separates drafts from confirmed
experiences. The additive, idempotent upgrade in `create_company_interview_schema`
defaults historical rows to confirmed and adds `onboarding_interview_version`.
The existing schema initializer applies this upgrade; no production database was
accessed during implementation. Apply the normal schema initialization in a
controlled deployment and verify the two columns before accepting draft traffic.

Draft answers use the existing owner-scoped `company_interview_answers` table.
Each confirmed text/skip is saved before advancing. A fresh browser session can
recover the draft for the active candidate; browser scope is rebound, not persisted
as authentication. Pending audio/transcripts are not confirmed evidence and are
not stored by this boundary. Block 5 will use per-question transcript acceptance.

Finalization locks the draft and validates persisted answers in the same
transaction that promotes it. V3 requires four core responses (explicit skips
remain unknown, never negative facts). Historical V1/V2 validation/text remains
unchanged. Final source projection contains user answers, not AI reflections.
Ordinary experience listings exclude drafts. No third experience store is added.

Retries with the same answer are idempotent; conflicting writes to an already
confirmed question fail instead of silently overwriting another tab's answer.
User-reviewed final edits are applied atomically with finalization. Failed writes
leave the draft recoverable and do not advance the question.

PostgreSQL uses the same transactional writes and additive column migration;
real PostgreSQL/browser restart and voice-provider E2E remain deployment checks.

## Block 5 runtime

New interviews started by profile onboarding explicitly select V3: four core
questions, zero to two material follow-ups, then source/reflection review.
V1/V2 handlers remain only for historical/resumed sessions and their regression
tests; they are not the default new production interview path.

Voice is transcribed only after recording confirmation. Its editable transcript
is saved only on Save & continue. Failed database writes preserve voice review;
transcript widget keys include the question ID to prevent cross-question reuse.
Reflection requires an explicit Review this experience action, including after
session loss. It can fail without losing source answers or preventing completion.
Finalization compares the reviewed answers to durable answers under the draft
lock, so another tab's unseen correction cannot be silently confirmed.

KEEP historical version readers/handlers; REPLACE the new-interview entrypoint
with V3; MERGE all persistence into the existing experience/answer repositories.
No new parallel experience authority or separate database was introduced.
