# Memory-First Company Interview V2

Global Beta remains 65%. V2 evolves the uncommitted V1 working tree; it does not
discard V1 source history. Browser feedback supplied by the user: after speaking,
the stop control was difficult to find. V2 also introduces quality/outcome recall,
an intermediate reflection and a tightly bounded adaptive step. The principle is
the user remembers, WorkPilot organizes, the user validates. Reduced self-presentation
pressure is a research-informed product design hypothesis, not a proven cognitive
or medical effect claimed by this implementation.

## Frozen questions

1. When I get in tomorrow, what do I do first?
2. And then? Take me through how the day usually goes from there.
3. Who am I usually dealing with during the day, and what do they normally need from me?
4. When something goes wrong, what usually happens? What do I do first? If an example comes to mind, tell me about it :D
5. What am I actually going to use to do the job — systems, tools, machines, documents, equipment, whatever it is? Which ones do I really need to know, and what do I use them for?
6. How do I know I’m doing the job right? What do people actually look at, check, measure or care about?
7. What can I normally decide or fix on my own, and when do I need to bring someone else in?
8. At the end of a good day, what have I actually got done? What would still be sitting there if I hadn’t done my job?

Final: Remember, I start tomorrow. Is there anything else about the job I should know?

One question per recall screen, with future questions/categories hidden. The core
bar measures eight completed answers and the counter names the current core step.
After core recall it stays complete and later recall says Almost done; final says
One last thing. There is no false fixed ten-question promise. Typical is nine,
maximum ten conversational questions; a review correction is additional source,
not another adaptive interview. Neutral acknowledgements are deterministic.

## Recorder findings

Inspected local Streamlit 1.61.0 metadata and audio_input.py signature/documentation.
Native audio_input supports visible label, help, stretch width, key and on_change.
It does not expose a dynamic stop-button label or a public recording-state API.
V2 uses full-width Tap to start talking, with Tap again when you're done immediately
above it and a same-control help tooltip. Accessible labeling is retained. No DOM
hacks, hidden native controls, third-party recorder or large frontend component.

NATIVE_RECORDER_UX_BLOCKER: unresolved until real desktop/mobile observation.
Guidance is improved, but fake tests cannot establish whether users now find Stop
immediately. Native playback may appear transiently before the capture rerun.
No application playback/re-record screen is added during normal recall. Only
technical failure exposes re-record. If this remains confusing in-browser, a custom
recorder requires a separate decision; these tests do not close that gate.

## State and authorization

Metadata -> eight fixed questions -> Show me what you've got -> transcription ->
reflection -> review/correction -> optional adaptive -> final -> source review ->
This looks right. Core capture makes no external call. Eight voice answers mean
eight independent transcription inputs; text/skip mean zero. The explicit processing
action triggers the injected reflection provider only after all core answers are
ready. No automatic retries. Failed transcription preserves all successful items;
failed reflection retains transcripts and offers Retry reflection, never re-record.

Additional voice answers each require Process this answer. No core transcription
or reflection repeats. Typed/skipped additions move directly to the next stage.
The default reflection provider is deliberately unavailable: no production LLM
adapter is enabled by this slice. The user can explicitly Continue with my source
answers, which omits derived interpretation/adaptive selection but still asks final
and requires source confirmation. This fail-soft decision avoids trapping a user
or presenting canned text as AI understanding. A later live adapter needs separate
configuration/authorization. Tests inject FakeReflection; it is never the default.

## Reflection contract

ReflectionProvider.generate accepts a prompt and returns JSON text. The prompt
builder includes ONLY company/start/end metadata and eight question IDs/text,
draft answer text and skip flags. No identity, audio, unrelated candidate data.

The result contains exactly interpretation, coverage, material_missing_dimension.
Interpretation arrays: understood, function, role_family, summary, capabilities,
tools, contexts, stakeholders, observed_work_patterns. Every item contains text,
nonempty uncertainty and support entries with question_id/exact source quote.
The parser rejects extra fields, duplicate JSON keys, malformed/oversized values,
missing dimensions, unknown/skipped source references and nonexistent quotes.

This structural/quotation gate cannot prove semantic entailment: a misleading
interpretation might cite a genuine but insufficient quote. No lexical skill/gap
heuristics pretend to solve that problem. All visible output remains Draft
interpretation with visible caveats. Human review remains necessary; no test of
a fake provider establishes real-model semantic reliability.

The prompt prohibits invented experience, metrics, achievements, tools, seniority,
expertise from occasional use, ownership from participation, skip-as-absence and
personality diagnosis. Market wording must remain defensible and uncertain where
appropriate. Observed in this experience is not a statement about personality.

## Adaptive policy

Coverage dimensions: core_work, context, stakeholders, tools_resources,
problem_resolution, concrete_evidence, autonomy_escalation, quality_standards,
outcomes_scale, work_patterns. Values are only SUFFICIENT/PARTIAL/INSUFFICIENT.
The provider may nominate one material_missing_dimension, and only if INSUFFICIENT.
PARTIAL alone never forces a question; even INSUFFICIENT without selection does not.
No arbitrary generated question field is accepted. ADAPTIVE_QUESTIONS is the fixed
approved bank in models/company_interview.py. No keyword matching selects questions.
Correction is preserved as source without rerunning interpretation or inventing a
new coverage judgment; the already selected follow-up can be skipped by the user.

## Source versus derived

Reflection stays session-only, never in the evidence table or compatibility prose.
The correction/addition is a separate REVIEW_CORRECTION record; it does not overwrite
the original fixed answers. Final review exposes every source text for factual
editing. Only This looks right saves the complete set atomically.

Version is company-interview-v2 for both interview and questions. V1 retains its
original seven questions/version. In-progress V1 session drafts can finish their
original flow without being relabeled as V2 or losing their recordings.
The additive source_kind column defaults to
FIXED_QUESTION for old rows, supporting FIXED_QUESTION, REVIEW_CORRECTION,
ADAPTIVE_QUESTION and FINAL_OPEN through repository validation. No historical text
is rewritten. Existing candidate/experience FK, RLS and revocation patterns remain.
No Pointer/Market Graph, ontology, concept IDs or edges were introduced.

career_story stays empty for guided records. day_to_day_narrative renders confirmed
source text only, with labels. confirmed_interview_answers carries rich kinds and
versions into the existing profile prompt; compatibility text is not duplicated.
Profile generation remains a later action and reflection is not authoritative.
Skip always means not provided, never gap/absence. No deterministic semantic
interpretation is added. Direction, Hiring Case, ranking and application prep are
unchanged.

Raw WAV bytes are session-only until successful transcription; no audio/prompt/
reflection/source text is logged or included in audit metadata. Identity/logout
cleanup uses the existing scoped _voice_ namespace. Unconfirmed drafts can be lost
on full session loss. Companies stay independently scoped. Privacy-safe events use
only fixed names, mode, step and allowlisted question IDs.

## Offline validation and remaining gate

Fixtures cover BPO customer support (including occasional SQL), electrician,
nurse, warehouse and a concise user. Fake-provider parser, state, persistence and
Streamlit AppTest tests cover both nine- and ten-question paths. No live adapter,
transcription, profile generation or production database was invoked.

Real browser checklist, still pending:

- Desktop/mobile: confirm the start/stop control is immediately understandable;
  microphone permission granted/denied/unavailable, valid/invalid audio.
- Confirm automatic advance, one question only, hidden future questions, core
  progress, no normal playback/re-record/transcript screen.
- Inject fake providers: eight voice/text/skip answers; no processing before click.
- Fail Q5: retry only Q5, retain others. Fail reflection: explicit retry without audio.
- Read both reflection layers/caveats, add correction, exercise zero/one adaptive.
- Process adaptive/final recordings separately; final always appears.
- Edit all source kinds, confirm, add another company; verify isolation and V1 reads.
- Exercise reruns, identity switch, logout and expiry with unconfirmed audio.
- Do not close NATIVE_RECORDER_UX_BLOCKER or advance global readiness until observed.
- Any live reflection/transcription/profile test needs separate authorization.

## Working-tree inventory

V1 files evolved/preserved: components/company_interview.py,
components/profile_onboarding.py, models/company_interview.py,
models/work_experience.py, services/company_interview.py,
services/candidate_onboarding_repository.py, services/database.py,
services/ai/candidate_profile_prompt_builder.py, services/onboarding_events.py,
tests/test_company_interview.py, tests/test_voice_onboarding_ui.py,
docs/memory_first_company_interview_v1.md.

New V2 files: services/company_reflection.py, tests/company_interview_fakes.py,
tests/test_company_reflection.py, docs/memory_first_company_interview_v2.md.

Fake-browser integration: render_profile_onboarding and render_company_interview
accept an explicit reflection_provider. Inject FakeReflection from the test helpers,
plus a fake transcription provider through VoiceTextInputs. Never configure that
test double as a production default. tests/test_voice_onboarding_ui.py contains
the complete isolated Streamlit AppTest fixture and both path regressions.
