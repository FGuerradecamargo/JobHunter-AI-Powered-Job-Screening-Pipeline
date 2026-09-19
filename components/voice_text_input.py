"""Session-only drafts; only explicit confirmation returns voice text for persistence."""
import hashlib
import time
import streamlit as st

from services.ai.voice_transcription import OpenAITranscriptionProvider, read_voice_config
from services.onboarding_events import OnboardingEvent

QUESTIONS = frozenset(('career_story', 'day_to_day', 'desired_next_work', 'enjoyed_work',
    'avoid_work', 'development_interests'))


def bind_scope(state, actor_id, active_id, candidate_id):
    if not all(isinstance(v, str) and v for v in (actor_id, active_id, candidate_id)):
        raise ValueError('onboarding_identity_required')
    scope = hashlib.sha256(repr((actor_id, active_id, candidate_id)).encode()).hexdigest()
    if state.get('_voice_owner') != scope:
        for key in list(state):
            if str(key).startswith(('_voice_', 'onboarding_step_', 'start_month_', 'start_year_', 'end_month_', 'end_year_', 'current_role_')):
                del state[key]
        state['_voice_owner'] = scope
    return scope


def answer_state(state, scope, question, initial=''):
    if question not in QUESTIONS or state.get('_voice_owner') != scope:
        raise ValueError('invalid_draft_scope')
    key = '_voice_draft_' + scope + '_' + question
    if key not in state:
        state[key] = dict(text=initial, accepted=initial, pending=False, mode='text', generation=0)
    return state[key]


class VoiceTextInputs:
    def __init__(self, scope, *, config=None, provider=None, events=None, ui=None):
        self.ui = ui or st
        self.scope, self.events = scope, events
        self.config = config or read_voice_config(secrets=self.ui.secrets)
        self.provider = provider or OpenAITranscriptionProvider(self.config, secrets=self.ui.secrets)
        self.step = 1

    def event(self, name, mode=None, *, once=False):
        key = '_voice_event_' + self.scope + '_' + name
        if once and self.ui.session_state.get(key):
            return
        self.ui.session_state[key] = True
        if self.events:
            started = self.ui.session_state.setdefault('_voice_started_' + self.scope, time.monotonic())
            self.events.record(OnboardingEvent(name, self.step, mode,
                min(604800, max(0, int(time.monotonic() - started)))))

    def pending(self, questions):
        return any(answer_state(self.ui.session_state, self.scope, q)['pending'] for q in questions)

    def clear(self, questions):
        for q in questions:
            draft = answer_state(self.ui.session_state, self.scope, q)
            draft.update(text='', accepted='', pending=False, generation=draft['generation'] + 1)

    def text_input(self, question, label, *, value='', **kwargs):
        key = '_voice_field_' + self.scope + '_' + question
        widget = key + '_widget'
        state = self.ui.session_state
        def changed():
            state[key] = state[widget]
            if str(state[key]).strip():
                self.event('first_answer_started', 'text', once=True)
        result = self.ui.text_input(label, value=state.get(key, value), key=widget, on_change=changed, **kwargs)
        state[key] = result
        return result

    def render(self, question, label, *, value='', height=120, placeholder=None):
        ui = self.ui
        draft = answer_state(ui.session_state, self.scope, question, value)
        prefix = '_voice_widget_' + self.scope + '_' + question + '_' + str(draft['generation'])
        ui.markdown('**' + label + '**')
        mode = 'text'
        if self.config.onboarding_enabled:
            mode = ui.radio('Answer format', ('text', 'voice'),
                index=0 if draft['mode'] == 'text' else 1, horizontal=True, key=prefix + '_mode',
                format_func=lambda x: 'Type answer' if x == 'text' else 'Record answer')
        if mode != draft['mode']:
            draft['mode'] = mode
            draft['generation'] += 1
            self.event('input_mode_selected', mode)
            ui.rerun()
        if mode == 'voice':
            ui.caption('Your recording is used only to turn your answer into text. Review the transcript before it is added to your profile.')
            if not self.config.transcription_enabled or not self.config.model:
                ui.info('Voice transcription is unavailable. You can type your answer below.')
            elif not callable(getattr(ui, 'audio_input', None)):
                ui.info('Microphone recording is unavailable. You can type your answer below.')
            else:
                ui.caption('Record up to 3 minutes per answer.')
                ui.caption('If microphone access is unavailable or denied, type your answer below.')
                audio = ui.audio_input('Record answer', key=prefix + '_audio')
                if audio is not None:
                    ui.audio(audio)
                    if not draft.get('mode_reported'):
                        self.event('input_mode_selected', 'voice')
                        draft['mode_reported'] = True
                    self.event('first_answer_started', 'voice', once=True)
                    if ui.button('Transcribe recording', key=prefix + '_transcribe'):
                        self.event('transcription_started', 'voice')
                        with ui.spinner('Transcribing...'):
                            result = self.provider.transcribe(audio.getvalue(), {}, allow_external_transcription=True)
                        if result.status == 'succeeded':
                            if not draft['pending']:
                                draft['accepted'] = draft['text']
                            draft.update(text=result.transcript_text, pending=True, generation=draft['generation'] + 1)
                            self.event('transcription_succeeded', 'voice')
                            ui.rerun()
                        else:
                            self.event('transcription_failed', 'voice')
                            ui.warning("We couldn't transcribe that recording. You can try again or type your answer.")
        if draft['pending']:
            ui.caption("Here's what I heard. Edit it, then accept or discard this draft.")
        text_key = prefix + '_text'
        def changed():
            draft['text'] = ui.session_state[text_key]
            if draft['text'].strip():
                if not draft.get('mode_reported'):
                    self.event('input_mode_selected', mode)
                    draft['mode_reported'] = True
                self.event('first_answer_started', mode, once=True)
        text = ui.text_area('Your answer', value=draft['text'], key=text_key,
            height=height, placeholder=placeholder, on_change=changed)
        draft['text'] = text
        if draft['pending']:
            if ui.button('Accept answer', key=prefix + '_accept'):
                draft.update(accepted=text, pending=False, generation=draft['generation'] + 1)
                self.event('first_answer_completed', 'voice', once=True)
                ui.rerun()
            if ui.button('Discard transcript', key=prefix + '_discard'):
                draft.update(text=draft['accepted'], pending=False, generation=draft['generation'] + 1)
                ui.rerun()
            return draft['accepted']
        return text
