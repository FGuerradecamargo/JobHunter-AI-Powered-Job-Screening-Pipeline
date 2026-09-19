import io
import json
import wave
from contextlib import nullcontext
from types import SimpleNamespace
import pytest

from models.transcription import TranscriptionResult
from services.ai.voice_transcription import VoiceConfig, OpenAITranscriptionProvider, read_voice_config, audio_duration
from services.onboarding_events import OnboardingEvent, OnboardingEventRepository, EVENTS
from components.voice_text_input import bind_scope, answer_state, VoiceTextInputs
from scripts.run_voice_transcription import main


def wav():
    data = io.BytesIO()
    with wave.open(data, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\x00\x00' * 160)
    return data.getvalue()


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    import socket
    def deny(*args, **kwargs):
        raise AssertionError('Network forbidden')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket.socket, 'connect_ex', deny)
    monkeypatch.setattr(socket, 'getaddrinfo', deny)


@pytest.mark.parametrize('enabled,authorized,code', [(False,False,'disabled'), (True,False,'not_authorized'), (False,True,'disabled'), (True,'true','not_authorized')])
def test_double_lock(enabled, authorized, code):
    made = []
    provider = OpenAITranscriptionProvider(VoiceConfig(True, enabled, 'fake'), transport_factory=lambda: made.append(1))
    result = provider.transcribe(wav(), {}, allow_external_transcription=authorized)
    assert result.issue_codes == (code,) and not made


@pytest.mark.parametrize('text', ['Trabalhei com suporte e pagamentos.', 'Trabajaba con clientes.', 'Je coordonnais les livraisons.'])
def test_original_language_not_translated(text):
    calls = []
    def transport(data, model):
        calls.append((data, model))
        return TranscriptionResult('succeeded', text, request_id='req_fake')
    result = OpenAITranscriptionProvider(VoiceConfig(True, True, 'fake'), transport_factory=lambda: transport).transcribe(wav(), {}, allow_external_transcription=True)
    assert result.transcript_text == text and len(calls) == 1
    assert result.request_id == 'req_fake' and result.duration > 0


@pytest.mark.parametrize('error,code', [(TimeoutError('PRIVATE'),'timeout'), (RuntimeError('PRIVATE'),'provider_unavailable')])
def test_error_is_sanitized(error, code, caplog):
    def transport(*args):
        raise error
    result = OpenAITranscriptionProvider(VoiceConfig(True,True,'fake'), transport_factory=lambda: transport).transcribe(wav(), {}, allow_external_transcription=True)
    assert result.issue_codes == (code,) and 'PRIVATE' not in repr(result) + caplog.text


@pytest.mark.parametrize('audio', [b'', b'not wav', b'x' * (10*1024*1024+1)], ids=['empty', 'invalid', 'oversize'])
def test_invalid_audio_never_calls(audio):
    made = []
    result = OpenAITranscriptionProvider(VoiceConfig(True,True,'fake'), transport_factory=lambda: made.append(1)).transcribe(audio, {}, allow_external_transcription=True)
    assert result.issue_codes == ('invalid_audio',) and not made


def test_defaults_and_dry_run():
    assert read_voice_config({}, {}) == VoiceConfig()
    out = io.StringIO()
    assert main([], config=VoiceConfig(True,True,'fake'), provider=object(), output=out) == 0
    plan = json.loads(out.getvalue())
    assert plan['planned_requests'] == 1 and plan['executed_requests'] == 0 and not plan['authorized']


def test_identity_change_clears_drafts_and_stale_scope_denied():
    state = {}
    a = bind_scope(state, 'actor', 'a', 'candidate-a')
    answer_state(state,a,'career_story')['text'] = 'PRIVATE'
    b = bind_scope(state, 'actor', 'b', 'candidate-b')
    assert 'PRIVATE' not in repr(state)
    with pytest.raises(ValueError):
        answer_state(state,a,'career_story')
    assert answer_state(state,b,'career_story')['text'] == ''


@pytest.mark.parametrize('event', sorted(EVENTS))
def test_event_content_allowlist(event):
    rows = []
    repo = OnboardingEventRepository('actor','active','candidate', repository=SimpleNamespace(record=lambda **kw: rows.append(kw)))
    repo.record(OnboardingEvent(event, 2, 'voice', 3))
    assert rows[0]['metadata'] == dict(step=2,input_mode='voice',elapsed_seconds=3)
    assert not set(rows[0]['metadata']) & {'transcript','audio','email','name','career_story'}
    with pytest.raises(ValueError):
        repo.record(OnboardingEvent(event,2,'PRIVATE TEXT'))


class Rerun(Exception):
    pass


class UI:
    def __init__(self):
        self.session_state, self.secrets = {}, {}
        self.click, self.text, self.mode, self.recording = '', None, 'text', None
        self.messages = []
    def markdown(self, *a, **kw): pass
    def caption(self, *a, **kw): pass
    def audio(self, *a, **kw): pass
    def info(self, text): self.messages.append(text)
    def warning(self, text): self.messages.append(text)
    def spinner(self, *a): return nullcontext()
    def radio(self, *a, **kw): return self.mode
    def audio_input(self, *a, **kw): return self.recording
    def button(self, label, **kw): return self.click == label
    def text_area(self, label, value, key, on_change, **kw):
        result = value if self.text is None else self.text
        self.session_state[key] = result
        on_change()
        return result
    def rerun(self): raise Rerun()


def test_voice_draft_must_be_edited_and_accepted_before_save():
    ui = UI()
    scope = bind_scope(ui.session_state,'u','u','c')
    provider = SimpleNamespace(transcribe=lambda *a, **kw: TranscriptionResult('succeeded','machine draft'))
    inputs = VoiceTextInputs(scope, ui=ui, config=VoiceConfig(True,True,'fake'), provider=provider)
    draft = answer_state(ui.session_state,scope,'career_story')
    ui.mode = draft['mode'] = 'voice'
    ui.recording, ui.click = io.BytesIO(wav()), 'Transcribe recording'
    with pytest.raises(Rerun): inputs.render('career_story','Story')
    ui.recording, ui.click, ui.text = None, '', 'edited original language'
    assert inputs.render('career_story','Story') == ''
    assert inputs.pending(('career_story',))
    ui.click = 'Accept answer'
    with pytest.raises(Rerun): inputs.render('career_story','Story')
    ui.click, ui.text = '', None
    assert inputs.render('career_story','Story') == 'edited original language'
    assert not inputs.pending(('career_story',))
    assert not any(isinstance(v, bytes) for v in draft.values())


def test_text_disabled_voice_and_failure_keep_text():
    ui = UI()
    scope = bind_scope(ui.session_state,'u','u','c')
    inputs = VoiceTextInputs(scope, ui=ui, config=VoiceConfig())
    ui.text = 'typed answer'
    assert inputs.render('career_story','Story') == 'typed answer'
    assert not inputs.pending(('career_story',))
    inputs.config = VoiceConfig(True,True,'fake')
    inputs.provider = SimpleNamespace(transcribe=lambda *a,**kw: TranscriptionResult('failed',issue_codes=('timeout',)))
    draft = answer_state(ui.session_state,scope,'career_story')
    ui.mode = draft['mode'] = 'voice'
    ui.recording, ui.click = io.BytesIO(wav()), 'Transcribe recording'
    assert inputs.render('career_story','Story') == 'typed answer'
    assert ui.recording is not None and any('try again' in m for m in ui.messages)


def test_native_sdk_adapter_uses_transcription_not_translation(monkeypatch):
    import openai
    calls = []
    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(text='Original words', _request_id='req_fake')
    def client(**kw):
        assert kw['max_retries'] == 0 and kw['timeout'] == 30
        return SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    monkeypatch.setattr(openai, 'OpenAI', client)
    monkeypatch.setenv('OPENAI_API_KEY','test-key-not-real')
    result = OpenAITranscriptionProvider(VoiceConfig(True,True,'fake')).transcribe(wav(), {}, allow_external_transcription=True)
    assert result.status == 'succeeded' and len(calls) == 1
    assert set(calls[0]) == {'model','file','response_format'}
    assert calls[0]['file'][0] == 'answer.wav'


def test_generation_uses_repository_answers_not_session_drafts():
    from services.candidate_profile_generation_service import CandidateProfileGenerationService
    from services.ai.candidate_profile_parser import REQUIRED_FIELDS
    from models.candidate_onboarding import CandidateOnboarding
    from models.work_experience import WorkExperience
    calls, saved = [], []
    output = {key: [] for key in REQUIRED_FIELDS}
    output.update(current_role='Support',current_level='Entry',professional_summary='Synthetic profile')
    def generate(prompt):
        calls.append(prompt)
        return json.dumps(output)
    onboarding = CandidateOnboarding('c', desired_next_work='Confirmed original answer')
    experience = WorkExperience('e','c','Synthetic','2020-01',None,'Confirmed story','Confirmed daily work')
    repo = SimpleNamespace(get_onboarding=lambda c:onboarding, list_work_experiences=lambda c:[experience])
    candidate = SimpleNamespace(get=lambda c:None, save=lambda c:saved.append(c))
    service = CandidateProfileGenerationService(SimpleNamespace(generate=generate),repo,candidate,
        SimpleNamespace(list_for_candidate=lambda c:[]))
    service.generate('c','Synthetic')
    assert 'Confirmed original answer' in calls[0] and 'Confirmed story' in calls[0]
    assert 'audio_bytes' not in calls[0] and onboarding.desired_next_work == 'Confirmed original answer'


def test_event_persistence_contains_only_technical_metadata():
    from services.database import get_connection
    OnboardingEventRepository('actor-test', 'active-test', 'candidate-test').record(
        OnboardingEvent('transcription_succeeded', 2, 'voice', 5))
    with get_connection() as connection:
        row = connection.execute('SELECT metadata_json FROM security_audit_events WHERE target_id = ?',
            ('candidate-test',)).fetchone()
    assert json.loads(row['metadata_json']) == {'step':2,'input_mode':'voice','elapsed_seconds':5}


def test_logout_cleanup_removes_only_onboarding_and_auth_state(monkeypatch):
    from services import session_auth
    state = {'_voice_draft_test': {'text':'private draft'}, '_voice_widget_audio': wav(),
        'onboarding_step_candidate': 2, 'unrelated': 'keep'}
    class Cookies(dict):
        def save(self): pass
    monkeypatch.setattr(session_auth, 'st', SimpleNamespace(session_state=state))
    monkeypatch.setattr(session_auth, 'cookies', Cookies())
    session_auth._clear_local_session()
    assert state == {'unrelated':'keep', 'reauthentication_required':True}
