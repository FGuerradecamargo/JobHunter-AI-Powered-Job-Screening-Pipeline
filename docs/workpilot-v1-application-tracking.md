# Block 9: application outcomes and interview rounds

InterviewRoundRepository is the official V1 round-based persistence boundary.
An active applied candidate/job relationship is required. Rounds are numbered
1..N without a fixed final-interview limit; schedule and interviewer identity
may remain unknown. A known interviewer role does not require a name.

Creation takes a transaction lock on the candidate/job relationship before
allocating the next sequence. A stable caller-supplied interview_id makes a
retried request idempotent; without one, each call explicitly creates a new
round. Terminal outcome writes coordinate on the same relationship lock.
Feedback is scoped by interview ID + candidate + job, including a composite
database foreign key. Free-text feedback/next steps stay source inputs, never
CandidateProfile updates. Internal line breaks and spacing are preserved.

No Response is an explicit, user-confirmed terminal state, not rejection. It
does not infer a reason or a capability gap. No elapsed-time automatic closure
is added. Outcome evidence records an unknown actor, not an employer rejection.
Offer can follow any interview; the historical final_interview label is still
readable for compatibility.

Schema changes are additive and idempotent for SQLite/PostgreSQL. Existing
single-row interview details/feedback are preserved unchanged (KEEP during
migration); the round repository is their intended REPLACE path. No invented
round history is backfilled. Full round editing/preparation UI cutover remains
integration work, including explicit migration of historical records. Existing
outcome UI now exposes No Response and the relaxed interview/offer transitions.

The real SQLite integration test exposed missing initialization of the existing
candidate_application_outcomes table on SQLite. The shared initialization now
ensures it exists with the existing PostgreSQL-compatible columns. No production
schema/data was accessed. Round tables apply server-only RLS and direct-role
revocation on PostgreSQL; live PostgreSQL and browser E2E remain unverified.
