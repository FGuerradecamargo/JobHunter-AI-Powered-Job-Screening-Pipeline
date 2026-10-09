"""One recall question per rerun; transcript review follows explicit processing."""
import streamlit as st
from models.company_interview import ACKNOWLEDGEMENTS, CORRECTION_QUESTION, V1_VERSION
from services.company_interview import (answer, process, confirmed_answers, current_question,
    advance_after_processing, review_reflection)
from services.company_reflection import reflect, ReflectionUnavailable, FIELDS
from services.ai.voice_transcription import audio_duration
from services.onboarding_events import OnboardingEvent
from models.company_interview import V3_VERSION, V3_QUESTIONS
from services.company_interview import (confirm_text, confirm_voice_transcript, discard_voice,
    finalize, save_correction, set_adaptive_dimensions, skip_question, transcribe_voice)
from services.company_reflection import reflect_v3
from models.company_interview import V4_VERSION, V4_QUESTIONS
from services.company_reflection import reflect_v4


def render_company_interview(draft, scope, repository, inputs, ui=None, reflection_provider=None):
    ui = ui or st
    if draft['scope'] != scope or ui.session_state.get('_voice_owner') != scope:
        raise ValueError('Invalid interview scope.')
    if draft['version'] == V4_VERSION:
        try:
            return render_v4_company_interview(draft, scope, repository, inputs, ui, reflection_provider)
        except Exception:
            ui.error('Your answer could not be saved. Please retry or reopen the interview.')
            return
    if draft['version'] == V3_VERSION:
        try:
            return render_v3_company_interview(draft, scope, repository, inputs, ui, reflection_provider)
        except Exception:
            ui.error('Your answer could not be saved. Please retry or reopen the interview.')
            return
    prefix = '_voice_company_' + draft['id']
    reflection_available = reflection_provider is not None
    reflection_provider = reflection_provider or ReflectionUnavailable()
    count = len(draft['answers'])
    def event(name, question_id=None, mode=None, once=False):
        marker = name + (question_id or '')
        seen = draft.setdefault('events', [])
        if once and marker in seen:
            return
        if inputs.events:
            inputs.events.record(OnboardingEvent(name, 2, mode, question_id=question_id))
        seen.append(marker)
    event('company_interview_started', once=True)
    core_total = 7 if draft['version'] == V1_VERSION else 8
    core_count = sum(a.get('kind', 'FIXED_QUESTION') == 'FIXED_QUESTION' for a in draft['answers'])
    ui.progress(core_count / core_total)
    ui.caption(f'Core conversation: {min(core_count + 1, core_total)} / {core_total}' if draft['stage'] == 'memory'
        else 'Core conversation complete' if draft['stage'] not in ('adaptive', 'final') else 'Almost done.')
    def run_reflection():
        event('company_reflection_started')
        with ui.spinner("Let me show you what I've got so far."):
            success = reflect(draft, scope, reflection_provider, authorized=True)
        event('company_reflection_completed' if success else 'company_reflection_failed')
    def run_processing():
        event('company_transcription_started')
        with ui.spinner("Got it. I'm turning your answers into text."):
            process(draft, scope, inputs.provider, inputs.config, authorized=True)
        event('company_transcription_failed' if draft['stage'] == 'failed' else 'company_transcription_completed')
        if draft['stage'] == 'reflection_pending':
            if reflection_available:
                run_reflection()
            else:
                draft['stage'] = 'reflection_failed'
                review_reflection(draft, scope)
    if draft.get('acknowledgement'):
        ui.write(draft['acknowledgement'])
    if draft['stage'] in ('memory', 'adaptive', 'final'):
        qid, question, kind = current_question(draft)
        event('company_question_viewed', qid, once=True)
        if kind == 'ADAPTIVE_QUESTION':
            event('company_adaptive_question_shown', qid, once=True)
        if kind == 'FINAL_OPEN':
            ui.caption('One last thing.')
        ui.write(question)
        key = prefix + '_' + qid
        def received(mode, value=''):
            answer(draft, scope, mode, value, repository=repository if draft.get('durable') else None)
            event('company_question_skipped' if mode == 'skip' else 'company_question_answered',
                qid, None if mode == 'skip' else mode)
            if kind == 'ADAPTIVE_QUESTION':
                event('company_adaptive_question_answered', qid)
            elif kind == 'FINAL_OPEN':
                event('company_final_question_answered', qid)
            draft.update(acknowledgement=ACKNOWLEDGEMENTS[count % len(ACKNOWLEDGEMENTS)], typing=False)
        voice = inputs.config.onboarding_enabled and not draft.get('typing', False)
        if voice:
            if callable(getattr(ui, 'audio_input', None)):
                ui.write("Tap again when you're done.")
                recording = ui.audio_input(
                    'Tap to start talking',
                    key=key + '_audio',
                    width='stretch',
                    help="Tap the same microphone control again to stop recording.",
                )

                if recording is not None:
                    ui.caption('Recording ready.')

                    if ui.button(
                        'Continue with recording',
                        key=key + '_voice_submit',
                        type='primary',
                    ):
                        try:
                            received('voice', recording.getvalue())
                        except ValueError:
                            ui.warning(
                                'Recording could not be used. '
                                'Try a new recording or type instead.'
                            )
                        else:
                            ui.rerun()

                    if ui.button(
                        'Discard recording and type instead',
                        key=key + '_type',
                        type='tertiary',
                    ):
                        draft['typing'] = True
                        ui.rerun()

                elif ui.button(
                    'type instead',
                    key=key + '_type',
                    type='tertiary',
                ):
                    draft['typing'] = True
                    ui.rerun()

            elif ui.button(
                'type instead',
                key=key + '_type',
                type='tertiary',
            ):
                draft['typing'] = True
                ui.rerun()
        else:
            text = ui.text_area('Your answer', key=key + '_text', max_chars=20000)
            if ui.button('Continue', key=key + '_submit'):
                if text.strip():
                    received('text', text)
                    ui.rerun()
        if ui.button('skip', key=key + '_skip', type='tertiary'):
            received('skip')
            ui.rerun()
        return
    if draft['stage'] in ('finish', 'finish_extra'):
        ui.write("Let me show you what I've got so far." if draft['stage'] == 'finish' else 'Got it. Ready to turn this answer into text?')
        ui.caption(' · '.join(f'{sum(a["mode"] == mode for a in draft["answers"])} {label}'
            for mode, label in [('voice', 'recorded'), ('text', 'typed'), ('skip', 'skipped')]))
        label = ('Finish this company' if draft['version'] == V1_VERSION else
            "Show me what you've got" if draft['stage'] == 'finish' else 'Process this answer')
        if ui.button(label, type='primary'):
            run_processing()
            ui.rerun()
        return
    if draft['stage'] == 'failed':
        ui.warning('Some answers could not be turned into text. Your other answers are safe.')
        for item in draft['answers']:
            if item['status'] == 'ready':
                continue
            key = prefix + item['question_id']
            ui.write(item['question_text'])
            recording = (ui.audio_input('Record again', key=key + '_retry_audio')
                if callable(getattr(ui, 'audio_input', None)) else None)
            if recording is not None:
                try:
                    audio_duration(recording.getvalue())
                    item['audio'] = recording.getvalue()
                except ValueError:
                    ui.warning('Recording could not be used.')
            replacement = ui.text_area('Type instead', key=key + '_replacement', max_chars=20000)
            if ui.button('Use typed answer', key=key + '_use') and replacement.strip():
                if draft.get('durable'):
                    from models.company_interview import ConfirmedCompanyAnswer
                    repository.save_company_answer(candidate_id=draft['candidate_id'], experience_id=draft['id'],
                        answer=ConfirmedCompanyAnswer(item['question_id'], item['question_text'], 'text', replacement,
                            False, draft['version'], draft['version'], item.get('kind', 'FIXED_QUESTION')))
                item.update(mode='text', text=replacement, status='ready', audio=None)
                advance_after_processing(draft)
                ui.rerun()
        if ui.button('Retry failed answers'):
            run_processing()
            ui.rerun()
        return
    if draft['stage'] in ('reflection_pending', 'reflection_failed'):
        ui.warning('The draft reflection is unavailable. Your answers are safe.')
        if reflection_available:
            if ui.button('Retry reflection'):
                run_reflection()
                ui.rerun()
        if ui.button('Continue with my source answers', type='tertiary'):
            draft['stage'] = 'reflection_failed'
            review_reflection(draft, scope)
            ui.rerun()
        return
    if draft['stage'] == 'reflection_review':
        ui.caption('Draft interpretation, not confirmed evidence. Observed in this experience.')
        for field in FIELDS:
            ui.write("What I've got so far" if field == 'understood' else
                'How the market would usually describe it' if field == 'function' else field.replace('_', ' ').capitalize())
            for claim in draft['reflection']['interpretation'][field]:
                ui.write('- ' + claim['text'])
                ui.caption(claim['uncertainty'])
        correction = ui.text_area(CORRECTION_QUESTION, key=prefix + '_correction', max_chars=20000)
        if ui.button('Continue', type='primary'):
            review_reflection(draft, scope, correction, repository=repository if draft.get('durable') else None)
            event('company_reflection_reviewed')
            ui.rerun()
        return
    if draft['stage'] == 'review':
        event('company_review_started', once=True)
        for item in draft['answers']:
            ui.write(item['question_text'])
            if item['mode'] == 'skip':
                ui.caption('Not provided')
            else:
                item['text'] = ui.text_area('Your answer', value=item['text'],
                    key=prefix + item['question_id'] + '_review', max_chars=20000)
        if ui.button('This looks right', type='primary'):
            try:
                repository.confirm_company_interview(candidate_id=draft['candidate_id'],
                    company=draft['company'], start_date=draft['start_date'], end_date=draft['end_date'],
                    answers=confirmed_answers(draft, scope), experience_id=draft['id'])
            except Exception:
                ui.error('Company could not be saved. Check your answers and try again.')
                return
            event('company_confirmed')
            event('company_interview_completed', once=True)
            for key in list(ui.session_state):
                if (str(key).startswith(prefix)
                        or str(key).startswith('_voice_field_' + scope + '_company')
                        or str(key) in {f'{field}_{draft["candidate_id"]}' for field in
                            ('company', 'start_month', 'start_year', 'end_month', 'end_year', 'current_role')}):
                    del ui.session_state[key]
            ui.session_state.pop('_voice_company_draft_' + scope, None)
            ui.rerun()


def render_v3_company_interview(
    draft,
    scope,
    repository,
    inputs,
    ui=None,
    reflection_provider=None,
):
    ui = ui or st
    if draft["scope"] != scope:
        raise ValueError("Invalid interview scope.")

    reflection_provider = (
        reflection_provider
        or ReflectionUnavailable()
    )
    prefix = "_voice_company_" + draft["id"]

    core_count = sum(
        item.source_kind == "FIXED_QUESTION"
        for item in draft["answers"]
    )
    ui.progress(min(core_count, len(V3_QUESTIONS)) / len(V3_QUESTIONS))

    if draft["stage"] == "question":
        qid, question, _ = current_question(draft)
        ui.caption(
            f"Core conversation: {min(core_count + 1, len(V3_QUESTIONS))} / "
            f"{len(V3_QUESTIONS)}"
            if core_count < len(V3_QUESTIONS)
            else "A quick follow-up"
        )
        ui.write(question)

        key = f"{prefix}_{qid}"
        voice = (
            inputs.config.onboarding_enabled
            and not draft.get("typing", False)
            and callable(getattr(ui, "audio_input", None))
        )

        if voice:
            recording = ui.audio_input(
                "Tap to start talking",
                key=key + "_audio",
                width="stretch",
            )
            if recording is not None:
                ui.caption("Recording ready.")
                if ui.button(
                    "Continue with recording",
                    key=key + "_voice_submit",
                    type="primary",
                ):
                    try:
                        with ui.spinner("Turning your answer into text..."):
                            transcribe_voice(
                                draft,
                                scope,
                                recording.getvalue(),
                                inputs.provider,
                                inputs.config,
                                authorized=True,
                            )
                    except Exception:
                        ui.warning(
                            "Recording could not be transcribed. "
                            "Try again or type instead."
                        )
                    else:
                        ui.rerun()
            if ui.button(
                "type instead",
                key=key + "_type",
                type="tertiary",
            ):
                draft["typing"] = True
                ui.rerun()
        else:
            text = ui.text_area(
                "Your answer",
                key=key + "_text",
                max_chars=20000,
            )
            if ui.button(
                "Save & continue",
                key=key + "_submit",
                type="primary",
            ):
                try:
                    confirm_text(
                        draft,
                        scope,
                        repository,
                        text,
                    )
                except ValueError:
                    ui.warning("Add an answer or skip.")
                else:
                    ui.rerun()

        if ui.button(
            "skip",
            key=key + "_skip",
            type="tertiary",
        ):
            skip_question(
                draft,
                scope,
                repository,
            )
            ui.rerun()
        return

    if draft["stage"] == "voice_review":
        pending = draft["pending_voice"]
        ui.write(pending["question_text"])
        transcript = ui.text_area(
            "Check the transcript",
            value=pending["transcript"],
            key=prefix + "_" + pending["question_id"] + "_voice_review",
            max_chars=20000,
        )
        ui.caption(
            "Nothing is saved until you confirm this text."
        )
        if ui.button(
            "Save & continue",
            type="primary",
            key=prefix + "_voice_confirm",
        ):
            confirm_voice_transcript(
                draft,
                scope,
                repository,
                transcript,
            )
            ui.rerun()
        if ui.button(
            "Record again",
            type="tertiary",
            key=prefix + "_voice_again",
        ):
            discard_voice(draft, scope)
            ui.rerun()
        return

    if draft["stage"] == "reflection_pending":
        if not ui.button('Review this experience', key=prefix + '_reflect', type='primary'):
            return
        try:
            with ui.spinner("Checking if anything important is missing..."):
                result = reflect_v3(
                    draft,
                    scope,
                    reflection_provider,
                    authorized=True,
                )
        except Exception:
            draft["reflection"] = None
            set_adaptive_dimensions(
                draft,
                scope,
                [],
            )
        else:
            draft["reflection"] = result
            set_adaptive_dimensions(
                draft,
                scope,
                result["material_missing_dimensions"],
            )
        ui.rerun()
        return

    if draft["stage"] == "review":
        ui.subheader("Here's what I understood")
        ui.caption('Draft interpretation, not confirmed evidence.')
        with ui.expander('Your confirmed source answers'):
            for source in draft['answers']:
                ui.write(source.question_text)
                ui.write('Not provided' if source.skipped else source.confirmed_text)
        reflection = draft.get("reflection")
        shown = 0
        if reflection:
            for field in FIELDS:
                for claim in reflection["interpretation"][field]:
                    ui.write("- " + claim["text"])
                    shown += 1
                    if shown >= 5:
                        break
                if shown >= 5:
                    break
        if not shown:
            ui.caption(
                "Your source answers are saved. "
                "WorkPilot will use them when building your profile."
            )

        correction = ui.text_area(
            CORRECTION_QUESTION,
            key=prefix + "_correction",
            max_chars=20000,
        )

        left, right = ui.columns(2)
        with left:
            if ui.button(
                "Save correction",
                use_container_width=True,
                disabled=not correction.strip(),
            ):
                save_correction(
                    draft,
                    scope,
                    repository,
                    correction,
                )
                ui.success("Correction saved.")
        with right:
            if ui.button(
                "Looks right",
                type="primary",
                use_container_width=True,
            ):
                if correction.strip():
                    save_correction(
                        draft,
                        scope,
                        repository,
                        correction,
                    )
                finalize(
                    draft,
                    scope,
                    repository,
                )
                for key in list(ui.session_state):
                    if str(key).startswith(prefix):
                        del ui.session_state[key]
                ui.session_state.pop(
                    "_voice_company_draft_" + scope,
                    None,
                )
                ui.rerun()
        return

    if draft["stage"] == "complete":
        ui.success("Experience saved.")


def render_v4_company_interview(draft, scope, repository, inputs, ui=None, reflection_provider=None):
    ui = ui or st
    if (draft["version"] != V4_VERSION or draft["scope"] != scope
            or ui.session_state.get("_voice_owner") != scope):
        raise ValueError("Invalid V4 interview scope.")
    prefix = "_voice_company_" + draft["id"] + "_"
    core_count = sum(a.source_kind == "FIXED_QUESTION" for a in draft["answers"])
    ui.progress(min(core_count, len(V4_QUESTIONS)) / len(V4_QUESTIONS))

    if draft["stage"] == "question":
        qid, question, _ = current_question(draft)
        ui.caption(f"Core conversation: {core_count + 1} / 3" if core_count < 3 else "A quick follow-up")
        ui.write(question)
        key = prefix + qid
        voice = (inputs.config.onboarding_enabled and not draft.get("typing", False)
                 and callable(getattr(ui, "audio_input", None)))
        if voice:
            recording = ui.audio_input("Tap to start talking", key=key + "_audio", width="stretch")
            if recording is not None and ui.button("Continue with recording", key=key + "_voice_submit", type="primary"):
                try:
                    with ui.spinner("Turning your answer into text..."):
                        transcribe_voice(draft, scope, recording.getvalue(), inputs.provider, inputs.config, authorized=True)
                except Exception:
                    ui.warning("Recording could not be transcribed. Try again or type instead.")
                else:
                    ui.rerun()
            if ui.button("type instead", key=key + "_type", type="tertiary"):
                draft["typing"] = True
                ui.rerun()
        else:
            text = ui.text_area("Your answer", key=key + "_text", max_chars=20000)
            if ui.button("Save & continue", key=key + "_submit", type="primary"):
                try:
                    confirm_text(draft, scope, repository, text)
                except ValueError:
                    ui.warning("Add an answer or skip.")
                else:
                    ui.rerun()
        if ui.button("skip", key=key + "_skip", type="tertiary"):
            skip_question(draft, scope, repository)
            ui.rerun()
        return

    if draft["stage"] == "voice_review":
        pending = draft["pending_voice"]
        ui.write(pending["question_text"])
        key = prefix + pending["question_id"]
        transcript = ui.text_area("Check the transcript", value=pending["transcript"],
                                  key=key + "_voice_review", max_chars=20000)
        ui.caption("Nothing is saved until you confirm this text.")
        if ui.button("Save & continue", key=prefix + "voice_confirm", type="primary"):
            confirm_voice_transcript(draft, scope, repository, transcript)
            ui.rerun()
        if ui.button("Record again", key=prefix + "voice_again", type="tertiary"):
            discard_voice(draft, scope)
            ui.session_state.pop(key + "_audio", None)
            ui.session_state.pop(key + "_voice_review", None)
            ui.rerun()
        return

    if draft["stage"] == "reflection_pending":
        error_key = prefix + "coverage_error"
        ui.caption("Checking whether important information is missing.")
        if ui.session_state.get(error_key):
            ui.warning("The coverage check is unavailable. Your confirmed answers are safe.")
        label = "Retry coverage check" if ui.session_state.get(error_key) else "Check for missing information"
        if ui.button(label, key=prefix + "reflect", type="primary"):
            try:
                with ui.spinner("Checking if anything important is missing..."):
                    reflect_v4(draft, scope, reflection_provider or ReflectionUnavailable(), authorized=True)
            except Exception:
                ui.session_state[error_key] = True
            else:
                ui.session_state.pop(error_key, None)
            ui.rerun()
        return

    if draft["stage"] == "review":
        ui.subheader("Your confirmed answers")
        for source in draft["answers"]:
            ui.write(source.question_text)
            ui.write("Not provided" if source.skipped else source.confirmed_text)
        correction = ui.text_area(CORRECTION_QUESTION, key=prefix + "correction", max_chars=20000)
        if ui.button("Save correction", key=prefix + "save_correction", disabled=not correction.strip()):
            save_correction(draft, scope, repository, correction)
            ui.success("Correction saved.")
        if ui.button("Looks right", key=prefix + "finalize", type="primary"):
            if correction.strip():
                save_correction(draft, scope, repository, correction)
            finalize(draft, scope, repository)
            _clear_v4_interview_state(draft, scope, ui)
            ui.rerun()
        return

    if draft["stage"] == "complete":
        if _clear_v4_interview_state(draft, scope, ui):
            ui.rerun()
        ui.success("Experience saved.")


def _clear_v4_interview_state(draft, scope, ui):
    if draft["version"] != V4_VERSION or draft["scope"] != scope or draft["stage"] != "complete":
        raise ValueError("V4 completion is required.")
    prefix = "_voice_company_" + draft["id"] + "_"
    for key in list(ui.session_state):
        if str(key).startswith(prefix):
            del ui.session_state[key]
    draft_key = "_voice_company_draft_" + scope
    active = ui.session_state.get(draft_key)
    if (isinstance(active, dict) and active.get("id") == draft["id"]
            and active.get("candidate_id") == draft["candidate_id"] and active.get("version") == V4_VERSION):
        del ui.session_state[draft_key]
        return True
    return False
