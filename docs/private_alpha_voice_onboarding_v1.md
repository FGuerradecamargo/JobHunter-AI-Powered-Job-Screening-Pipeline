# Private Alpha Voice and Text Onboarding V1

## User flow

Existing four-step onboarding remains. Step 1 collects basic constraints;
Step 2 keeps company/dates structured and offers voice or text for career story
and daily work. Step 3 offers the same alternative for each of four direction
answers. All questions remain answerable with text; four recordings are never
required. Step 4 reviews persisted answers and uses the existing profile builder.

The introduction invites natural, original-language answers. Native Streamlit
1.61.0 audio_input provides browser microphone capture. Playback is offered
before the explicit Transcribe recording action. Text remains available below
voice controls, including when permission is denied or capture is unsupported.
No new dependency, custom audio component, chatbot or text-to-speech was added.

## Confirmation and privacy

Audio -> in-memory transcription -> editable draft -> Accept answer -> existing
Add this experience / Review profile save action. Pending transcripts block
saving the affected step. Discard restores the prior answer. Machine text never
automatically reaches the repository, Candidate Profile or Career Memory.

Typed answers are confirmed by the existing explicit save/continue action.
Voice has no privileged evidence state. Profile generation reads only existing
persisted onboarding records, not session drafts. Original answers are retained;
transcription uses the transcription endpoint, not translation, with no forced
language selector or enrichment prompt. Future normalized-English interpretation
belongs in a separately versioned derived profile representation with source
links, never overwriting original onboarding answers.

No application audio files, database audio columns, payload logs or analytics
audio are created. Streamlit temporarily holds UploadedFile/browser recording
data in session/media memory. Widget generation changes after success, discard,
or mode changes detach the recording on rerun; failed attempts retain it for
retry. Logout/expiry clears onboarding draft keys. Framework/browser memory
release is not an instantaneous deletion guarantee. Provider retention is not
controlled or promised here. Only minimum audio bytes and technical parameters
are sent after authorization; no name, CV or profile is supplied.

## Drafts and isolation

Narrative and basic text drafts have non-widget session keys and survive ordinary
reruns and step navigation. Keys are bound to authenticated user, active user
and candidate; switching identity removes previous drafts. Page authorization
and candidate checks remain in place. Logout/expiry clears the same keys.
Confirmed answers are saved through the existing repository. A new session
resumes from persisted progress; unconfirmed text/recordings do NOT survive
session loss, idle expiry, browser reconnection to a new session or server restart.
Date/select widgets may need reselection after leaving a step before saving.
There is no new durable draft system or database migration.

## Provider and configuration

`models/transcription.py` defines SDK-neutral result/protocol types.
`services/ai/voice_transcription.py` implements a lazy OpenAI adapter using the
installed SDK. Environment values take precedence over Streamlit secrets.

- VOICE_ONBOARDING_ENABLED: false by default; enables microphone UI.
- VOICE_TRANSCRIPTION_ENABLED: false by default; permits transcription transport.
- VOICE_TRANSCRIPTION_MODEL: required, no implicit model or fallback.
- OPENAI_API_KEY: resolved only after both transcription locks, never logged.

External transcription requires enabled configuration AND
allow_external_transcription=True on the explicit action. UI passes authorization
only on Transcribe recording, not rendering/recording/rerunning. Harness requires
--live AND --confirm-external-ai. SDK has zero retries and a finite 30s timeout.
Native PCM WAV only: nonempty, at most 10 MiB and 180 seconds. Unsupported or
truncated audio fails before transport. No paid call was made to verify model
availability, account access or language quality.

Failure is sanitized and recoverable: retry or type. Raw provider exceptions,
audio and transcript never enter diagnostic logs. The OpenAI SDK signature was
checked locally; no online documentation or key-validation request was made.

## Activation instrumentation

First-party `OnboardingEventRepository` reuses the existing server audit storage,
without a third-party tracker or new schema. Allowlisted events:
onboarding_started, onboarding_step_viewed, first_answer_started,
first_answer_completed, transcription_started, transcription_succeeded,
transcription_failed, input_mode_selected, onboarding_step_completed,
onboarding_completed, candidate_profile_created; abandonment_step is accepted
but not automatically inferred from browser closing.

Metadata is limited to step, input_mode (voice/text), bounded elapsed seconds
and existing internal actor/active/candidate IDs. No transcript, answers, audio,
names, emails, CV or job-history text. First-event deduplication is session-only.
Mode describes the current input action, never a permanent user preference.
Storage failure emits a generic warning and cannot block onboarding.

## Controlled harness

Dry-run (no audio file required, no network):

```powershell
python scripts/run_voice_transcription.py
```

Observed plan: provider=openai, model unset, no audio supplied, authorized=false,
planned_requests=1, executed_requests=0. Optional --audio validates a local WAV
and prints duration/presence, never the path/content. Fake tests synthesize
in-memory silence, so no binary fixture or downloaded sample is necessary.

The following WOULD perform at most ONE paid transcription after configuration
and human approval. It was NOT run; supply a consented local WAV:

```powershell
python scripts/run_voice_transcription.py --audio C:\Temp\synthetic-answer.wav --live --confirm-external-ai
```

No retries. Harness prints normalized status/request ID, not transcript.
It does not create a profile or run a second AI operation.

## Files and limitations

Added: `components/voice_text_input.py`, `models/transcription.py`,
`services/ai/voice_transcription.py`, `services/onboarding_events.py`,
`scripts/run_voice_transcription.py`, `tests/test_voice_onboarding.py`,
`tests/test_voice_onboarding_ui.py`, this document.
Updated: `components/profile_onboarding.py`, `pages/3_Profile.py`,
`services/session_auth.py` (only cleanup of new onboarding session keys).
Profile client construction is lazy so missing AI credentials do not block text
collection. Existing profile generation remains separately user-triggered.

Automated UI tests exercise text completion and fake transcript confirmation.
Real browser microphone permissions, mobile recording/playback, account model
availability and real transcription quality remain untested. No production app
or database was opened. A controlled real voice test requires configured flags,
model, credential and explicit human authorization, plus a consented recording.
Alpha readiness for five unknown users still needs those real-browser checks.

## Offline validation result

- Final focused voice/UI and semantic adapter tests: 98 passed (fake transports).
- Expanded onboarding/auth/profile/semantic regression: 574 passed.
- Final full suite: 1654 passed, 2 skipped in 58.47 seconds.
- Network connections and DNS were blocked; test database isolation was active.
- Both dry-runs executed zero requests. No external AI/provider calls, production
  access, key validation, commit or push occurred.
- git diff --check and untracked-file whitespace checks passed; LF/CRLF warnings
  only. Historical reports and reviewed fixtures were verified unchanged.
