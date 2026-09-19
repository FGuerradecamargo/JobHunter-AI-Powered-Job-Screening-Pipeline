# Memory-First Company Interview V1

Historical V1 design. Superseded before commit by
[Memory-First Company Interview V2](memory_first_company_interview_v2.md).
The original question texts and version remain supported for historical data.

Global Beta readiness remains 65%. Implementation and offline tests do not advance
the real-browser gate. This is a product design hypothesis for Alpha, not a claim
of scientifically proven cognitive benefits.

## Principle and frozen questions

The user remembers; WorkPilot organizes. Company and month/year dates remain
structured. One fixed question is rendered per rerun, without future categories.

1. When you got to work, what did you usually do first?
2. And after that? How did the day usually go?
3. Who would usually come to you during the day? What did they need from you?
4. When something went wrong, what usually happened? What did you do?
5. When you were doing the job, what did you usually have open or in front of you?
6. When something different came up, did you usually sort it out yourself or call someone? How did that work?
7. Remember, I’m starting tomorrow. Is there anything about this job I still haven’t asked that you think I should know?

## Recall

Voice is default when VOICE_ONBOARDING_ENABLED is enabled. Native Streamlit
audio_input captures one WAV; successful validation stores bytes in session memory
and immediately reruns to the next question. No separate Next, playback component,
transcript, extracted claims, or normal re-record action is rendered. The browser
may transiently show its native recorder controls before that rerun; verify this
in the controlled browser check below. The text fallback and tertiary skip remain
available. Text uses one input and Continue. Skip is NOT PROVIDED, never a gap or
confirmed absence. Empty typed answers do not advance.

Progress shows the current question ordinal and fraction completed (0/7 before
answer one; 7/7 after answer seven). Deterministic acknowledgements cycle through
Uhum., Got it., Okay., Nice., Right., Got it., Okay. They acknowledge receipt only.
No company narrative is interpreted during recall.

## Processing and confirmation

Finish this company is the first processing action. Seven voice answers require
seven independent transcription requests; text and skip require zero. No audio
concatenation. The existing provider's configuration, explicit authorization,
finite timeout, original language and zero retry rules remain in force. There is
no live transport call from capture or rerun. Failed answers are retried only on
explicit action; successful transcripts survive and are never re-requested.
Only technically failed answers expose Record again, or replacement typed text.

Once every answer is ready, all questions and editable transcripts appear for
review. Skips remain Not provided. Only This looks right persists sources, in
one transaction with the experience. Blank non-skipped confirmed answers fail
validation. Machine transcripts alone are not durable evidence.

## Storage and authority

company_interview_answers is additive, with candidate and experience ownership,
question ID/text/version, interview version, answer mode, confirmed text, skip
flag and confirmation time. A composite foreign key enforces experience ownership.
PostgreSQL enables server-only RLS and revokes public/anon/authenticated access.
SQLite uses the same data contract. No historical experience is rewritten or
reinterpreted. The primary key indexes owner/experience/question; a supporting
unique parent ownership index enables the composite FK.

Confirmed Q&A is the guided source of truth. career_story stays empty;
day_to_day_narrative is a deterministic labeled rendering of non-skipped sources.
It is compatibility text, not a second independent fact. WorkExperience carries
confirmed_interview_answers; the profile prompt receives these with company
metadata and suppresses duplicate narrative projection. Existing legacy records
retain their original narratives. Candidate statements do not automatically
establish proven capabilities or objective truth. No keyword inference is added.

Session draft identity binds actor, active user, candidate, company draft and
question. Raw audio never enters the database, logs, audit events or profile.
Successful transcription drops draft audio. Confirmation removes interview
widgets/draft and company metadata. Identity changes, logout and session expiry
clear the existing _voice_ state namespace. Confirmed companies remain durable
and independent. Each additional company starts a fresh draft.

First-party audit events contain fixed event names, step, mode and question ID
only. No company names, answers, audio, prompts or provider errors are recorded.

## Alpha limitations and browser gate

Unconfirmed audio/text and review edits are session-only, so full session loss
loses unconfirmed work. Native recorder permission/codec/visual timing is not
established by AppTest or fake UI tests. Processing is synchronous, bounded per
request; interrupted batches retain completed items in the live session and
require explicit action again. An in-flight external request cannot be undone.
Disabled transcription permits typed replacement of failed voice answers.

Controlled browser checklist, still required:

- On desktop and mobile, check company/date input and seven one-question screens.
- Enable voice in an approved test environment; test microphone grant and denial,
  automatic advance with no intervening playback/review, and type/skip fallback.
- Check 3-minute/10MiB WAV limits, progress, acknowledgements and exact final copy.
- With fake transport first, finish mixed voice/text/skip; fail one question,
  replace only that recording, retry and verify the other transcripts survive.
- Edit a transcript, confirm, add another company; verify separate rich sources.
- Navigate away/rerun, switch identity, log out and expire session; verify audio
  is gone and confirmed data remains scoped. Check legacy profile generation
  using a fake LLM, with no production writes.
- Any live transcription or profile generation requires separate authorization.

No Career Journey, semantic engine, Hiring Case, ranking, direction questions or
application preparation behavior is redesigned.

## Implementation files

- components/company_interview.py (new recall/processing/review renderer)
- components/profile_onboarding.py (experience-step integration only)
- models/company_interview.py (new frozen questions and confirmed answer contract)
- models/work_experience.py (optional rich sources, legacy defaults preserved)
- services/company_interview.py (new session state transitions and deferred processing)
- services/candidate_onboarding_repository.py (atomic scoped confirmation and loading)
- services/database.py (additive schema and server-only hardening)
- services/ai/candidate_profile_prompt_builder.py (rich source without duplicate projection)
- services/onboarding_events.py (allowlisted first-party interview events)
- tests/test_company_interview.py (new offline data and cognitive UI tests)
- tests/test_voice_onboarding_ui.py (updated complete onboarding regression)
- docs/memory_first_company_interview_v1.md (this document)
