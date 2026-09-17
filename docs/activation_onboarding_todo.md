# P0: Low-friction onboarding

Documentation only. No UI, routes, provider, transcription or audio API is implemented.

## Problem and goal

Users may abandon registration when asked to type substantial professional history.
Increase ONBOARDING_STARTED -> CANDIDATE_PROFILE_CREATED. Collect enough to start,
not an exhaustive biography; progressively enrich the profile afterward.

## Proposed introduction

"This takes about 5 minutes.
Answer as naturally and honestly as you can.
You don't need CV language or perfect wording.
You can speak or type in any language.
WorkPilot will organize what you share, and you'll review it before it becomes part of your profile.
You can stop and continue later."

## Principles and initial questions

- Voice or text in any spoken/written language.
- Preserve the transcript in the original language; internal normalization may use English.
- User confirmation is required before persistent Career Memory mutation.
- Autosave drafts separately from confirmed Career Memory; allow resume later.
- Start with enough context for first opportunities; enrich progressively.

1. What do you do today?
2. What have you done before that feels most relevant?
3. Where would you like to go next?
4. Is there anything important WorkPilot should consider?

## Future flow

Voice/text -> transcription if needed -> structured interpretation -> user confirmation
-> Career Memory -> Candidate Profile -> first opportunities.

## Instrumentation TODO

Capture signup, onboarding_started, first_answer_started, first_answer_completed,
input_mode (voice/text), onboarding_step, abandonment_step, onboarding_completed,
candidate_profile_created, first_opportunities_shown and elapsed time.
Do not collect raw audio, transcript content or private answers in analytics unnecessarily.
Define retention and consent before implementing audio storage or transcription providers.
