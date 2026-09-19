import io
import wave
from dataclasses import asdict
from types import SimpleNamespace
from contextlib import nullcontext
import pytest
from models.company_interview import QUESTIONS, ACKNOWLEDGEMENTS, validate_answers
from models.transcription import TranscriptionResult
from services.company_interview import start_interview, answer, process, confirmed_answers, review_reflection
from services.company_reflection import reflect
from tests.company_interview_fakes import FakeReflection
from services.ai.voice_transcription import VoiceConfig
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from services.database import get_connection, create_company_interview_schema
from components.company_interview import render_company_interview
from components.voice_text_input import bind_scope


def wav():
    data = io.BytesIO()
    with wave.open(data, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b'\x00\x00' * 160)
    return data.getvalue()


class Provider:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def transcribe(self, data, metadata, **kw):
        self.calls.append((data, metadata, kw))
        if metadata['question_id'] == self.fail:
            raise TimeoutError('PRIVATE ERROR')
        return TranscriptionResult('succeeded', 'Original ' + metadata['question_id'])


def draft():
    return start_interview('scope', 'c', 'Synthetic Operations Co', '2020-01', None)


def complete(d, mode='voice'):
    for _ in QUESTIONS:
        answer(d, 'scope', mode, wav() if mode == 'voice' else 'checked email')


def finish_sources(d):
    assert reflect(d, 'scope', FakeReflection(), authorized=True)
    review_reflection(d, 'scope')
    answer(d, 'scope', 'skip')


def test_deferred_seven_independent_requests_and_raw_audio_discarded(caplog):
    d, p = draft(), Provider()
    complete(d)
    assert not p.calls and d['stage'] == 'finish'
    with pytest.raises(ValueError):
        process(d, 'scope', p, VoiceConfig(True, True, 'fake'))
    process(d, 'scope', p, VoiceConfig(True, True, 'fake'), authorized=True)
    assert len(p.calls) == 8
    assert [m['question_id'] for _, m, _ in p.calls] == [f'q{i}' for i in range(1, 9)]
    assert all(kw['allow_external_transcription'] is True for _, _, kw in p.calls)
    assert d['stage'] == 'reflection_pending' and all(a['audio'] is None for a in d['answers'])
    with pytest.raises(ValueError):
        process(d, 'scope', p, VoiceConfig(True, True, 'fake'), authorized=True)
    assert caplog.text == ''


def test_failed_only_explicit_retry_preserves_success(caplog):
    d, p = draft(), Provider('q3')
    complete(d)
    process(d, 'scope', p, VoiceConfig(True, True, 'fake'), authorized=True)
    assert d['stage'] == 'failed'
    assert sum(a['status'] == 'ready' for a in d['answers']) == 7
    assert len(p.calls) == 8
    p.fail = None
    process(d, 'scope', p, VoiceConfig(True, True, 'fake'), authorized=True)
    assert len(p.calls) == 9 and p.calls[-1][1]['question_id'] == 'q3'
    assert d['answers'][0]['text'] == 'Original q1'
    assert 'PRIVATE' not in caplog.text


@pytest.mark.parametrize('mode', ['text', 'skip'])
def test_text_skip_never_transcribed(mode):
    d, p = draft(), Provider()
    complete(d, mode)
    process(d, 'scope', p, VoiceConfig(), authorized=True)
    finish_sources(d)
    records = confirmed_answers(d, 'scope')
    validate_answers(records)
    assert not p.calls
    assert all(r.skipped == (mode == 'skip') for r in records[:-1])
    assert not any('gap' in asdict(r) for r in records)


def test_config_gate_and_invalid_audio():
    d, p = draft(), Provider()
    with pytest.raises(ValueError):
        answer(d, 'scope', 'voice', b'corrupt')
    assert not d['answers']
    complete(d)
    process(d, 'scope', p, VoiceConfig(), authorized=True)
    assert not p.calls and d['stage'] == 'failed'


def test_identity_switch_clears_audio_and_rejects_foreign_scope():
    state = {}
    scope = bind_scope(state, 'u', 'u', 'c')
    d = start_interview(scope, 'c', 'Synthetic', '2020-01', None)
    answer(d, scope, 'voice', wav())
    state['_voice_company_draft_' + scope] = d
    bind_scope(state, 'other', 'other', 'other')
    assert '_voice_company_draft_' + scope not in state
    with pytest.raises(ValueError):
        answer(d, 'foreign', 'skip')


def test_confirmation_atomic_scoped_rich_source_and_legacy_projection():
    from models.candidate import Candidate
    from services.candidate_repository import CandidateRepository
    CandidateRepository().save(Candidate(id='c', name='Synthetic', current_role='', current_level='', professional_summary=''))
    CandidateRepository().save(Candidate(id='other', name='Other', current_role='', current_level='', professional_summary=''))
    repo = CandidateOnboardingRepository()
    d = draft()
    details = ['checked email', 'reviewed spreadsheets', 'checked previous shift status',
        'started customer calls', 'internal and external customers', 'managed people flow', '', '']
    for text in details:
        answer(d, 'scope', 'text' if text else 'skip', text)
    assert repo.list_work_experiences('c') == []
    process(d, 'scope', Provider(), VoiceConfig(), authorized=True)
    assert repo.list_work_experiences('c') == []
    finish_sources(d)
    records = confirmed_answers(d, 'scope')
    kw = dict(candidate_id='c', company=d['company'], start_date=d['start_date'], end_date=None,
        answers=records, experience_id=d['id'])
    repo.confirm_company_interview(**kw)
    repo.confirm_company_interview(**kw)
    exp = repo.list_work_experiences('c')[0]
    assert exp.career_story == '' and len(exp.confirmed_interview_answers) == 9
    assert '[Q1]' in exp.day_to_day_narrative and '[Q7]' not in exp.day_to_day_narrative
    assert repo.list_company_answers('other', d['id']) == []
    with pytest.raises(ValueError):
        repo.confirm_company_interview(**dict(kw, candidate_id='other'))
    with get_connection() as conn:
        create_company_interview_schema(conn)
        assert conn.execute('SELECT COUNT(*) AS n FROM company_interview_answers').fetchone()['n'] == 9
        assert 'audio' not in str(dict(conn.execute('SELECT * FROM company_interview_answers LIMIT 1').fetchone()))
    from services.ai.candidate_profile_prompt_builder import build_candidate_profile_prompt
    from models.candidate_onboarding import CandidateOnboarding
    prompt = build_candidate_profile_prompt(CandidateOnboarding(candidate_id='c'), [exp])
    assert 'confirmed_interview_answers' in prompt and 'checked email' in prompt
    assert prompt.count('checked email') == 1
    repo.delete_work_experience(d['id'], 'c')
    assert not repo.list_company_answers('c', d['id'])


class Rerun(Exception):
    pass


class UI:
    def __init__(self, click=None, recording=None):
        self.session_state = {'_voice_owner': 'scope'}
        self.click, self.recording = click, recording
        self.shown, self.buttons, self.areas, self.audio_labels, self.progresses = [], [], [], [], []
    def progress(self, x): self.progresses.append(x)
    def caption(self, x): self.shown.append(x)
    def write(self, x): self.shown.append(x)
    def warning(self, x): self.shown.append(x)
    def error(self, x): self.shown.append(x)
    def button(self, label, **kw):
        self.buttons.append(label)
        return label == self.click
    def audio_input(self, label, **kw):
        self.audio_labels.append(label)
        return self.recording
    def text_area(self, label, **kw):
        self.areas.append(label)
        return kw.get('value', 'Typed memory')
    def spinner(self, *a): return nullcontext()
    def rerun(self): raise Rerun()


@pytest.mark.parametrize('index', range(8))
def test_one_question_voice_default_progress_no_review_or_future(index):
    d, p, ui = draft(), Provider(), UI()
    for _ in range(index):
        answer(d, 'scope', 'skip')
    inputs = SimpleNamespace(config=VoiceConfig(True, True, 'fake'), provider=p, events=None)
    render_company_interview(d, 'scope', None, inputs, ui)
    assert QUESTIONS[index] in ui.shown
    assert not any(q in ui.shown for q in QUESTIONS[index + 1:])
    assert ui.progresses == [index / 8]
    assert ui.audio_labels == ['Tap to start talking'] and not ui.areas
    assert "Tap again when you're done." in ui.shown
    assert 'skip' in ui.buttons and 'type instead' in ui.buttons
    assert 'Record again' not in ui.buttons and "I don't remember" not in str(ui.shown)
    assert not p.calls


def test_audio_capture_advances_without_provider_or_playback():
    d, p = draft(), Provider()
    ui = UI(recording=io.BytesIO(wav()))
    inputs = SimpleNamespace(config=VoiceConfig(True, True, 'fake'), provider=p, events=None)
    with pytest.raises(Rerun):
        render_company_interview(d, 'scope', None, inputs, ui)
    assert len(d['answers']) == 1 and not p.calls
    assert d['acknowledgement'] == ACKNOWLEDGEMENTS[0]
    assert not ui.areas
    ui = UI()
    render_company_interview(d, 'scope', None, inputs, ui)
    assert ACKNOWLEDGEMENTS[0] in ui.shown


def test_finish_then_failed_only_rerecord_then_edit_review():
    d, p = draft(), Provider('q2')
    complete(d)
    inputs = SimpleNamespace(config=VoiceConfig(True, True, 'fake'), provider=p, events=None)
    ui = UI()
    render_company_interview(d, 'scope', None, inputs, ui)
    assert not p.calls and not ui.areas
    with pytest.raises(Rerun):
        render_company_interview(d, 'scope', None, inputs, UI("Show me what you've got"), FakeReflection())
    ui = UI()
    render_company_interview(d, 'scope', None, inputs, ui)
    assert ui.audio_labels == ['Record again']
    assert QUESTIONS[1] in ui.shown and QUESTIONS[0] not in ui.shown
    p.fail = None
    with pytest.raises(Rerun):
        render_company_interview(d, 'scope', None, inputs, UI('Retry failed answers'), FakeReflection())
    review_reflection(d, 'scope')
    answer(d, 'scope', 'skip')
    ui = UI()
    render_company_interview(d, 'scope', None, inputs, ui)
    assert len(ui.areas) == 8 and not ui.audio_labels
    assert 'This looks right' in ui.buttons


def test_final_frozen():
    from models.company_interview import FINAL_QUESTION
    assert FINAL_QUESTION == 'Remember, I start tomorrow. Is there anything else about the job I should know?'


def test_postgres_schema_is_additive_and_server_only(monkeypatch):
    import services.database as db
    statements = []
    monkeypatch.setattr(db, 'is_postgres', lambda: True)
    connection = SimpleNamespace(execute=lambda sql, *args: statements.append(sql))
    create_company_interview_schema(connection)
    sql = '\n'.join(statements)
    assert 'CREATE TABLE IF NOT EXISTS' in sql
    assert 'ENABLE ROW LEVEL SECURITY' in sql and 'FROM PUBLIC' in sql
    assert 'FROM anon' in sql and 'FROM authenticated' in sql
    assert not any(word in sql for word in ('DROP TABLE', 'UPDATE ', 'DELETE FROM'))


def test_multiple_companies_independent_and_empty_review_rejected():
    from dataclasses import replace
    d1, d2 = draft(), draft()
    assert d1['id'] != d2['id']
    complete(d1, 'text')
    assert d2['answers'] == []
    process(d1, 'scope', Provider(), VoiceConfig(), authorized=True)
    finish_sources(d1)
    records = confirmed_answers(d1, 'scope')
    records[0] = replace(records[0], confirmed_text='')
    with pytest.raises(ValueError):
        validate_answers(records)


def test_logout_removes_company_audio(monkeypatch):
    import services.session_auth as auth
    state = {'_voice_company_draft_scope': draft(), 'current_user': object()}
    complete(state['_voice_company_draft_scope'])
    monkeypatch.setattr(auth.st, 'session_state', state)
    class Cookies(dict):
        def save(self): pass
    monkeypatch.setattr(auth, 'cookies', Cookies())
    auth._clear_local_session()
    assert not any(k.startswith('_voice_') for k in state)


def test_profile_generation_receives_rich_sources_with_fake_llm():
    from models.work_experience import WorkExperience
    from models.candidate_onboarding import CandidateOnboarding
    from services.candidate_profile_generation_service import CandidateProfileGenerationService
    d = draft()
    complete(d, 'text')
    process(d, 'scope', Provider(), VoiceConfig(), authorized=True)
    finish_sources(d)
    experience = WorkExperience('exp', 'c', 'Synthetic Co', '2020-01', None, '',
        'compatibility projection must not duplicate', confirmed_answers(d, 'scope'))
    captured = []
    def generate(prompt):
        captured.append(prompt)
        raise ValueError('fake stop after prompt inspection')
    service = CandidateProfileGenerationService(SimpleNamespace(generate=generate),
        SimpleNamespace(get_onboarding=lambda c: CandidateOnboarding(candidate_id=c),
            list_work_experiences=lambda c: [experience]), None,
        SimpleNamespace(list_for_candidate=lambda c: []))
    with pytest.raises(ValueError, match='fake stop'):
        service.generate('c', 'Synthetic')
    assert len(captured) == 1
    assert 'confirmed_interview_answers' in captured[0]
    assert 'compatibility projection must not duplicate' not in captured[0]


def test_question_analytics_metadata_is_allowlisted():
    from services.onboarding_events import OnboardingEvent, OnboardingEventRepository
    captured = []
    sink = OnboardingEventRepository('u', 'u', 'c', repository=SimpleNamespace(record=lambda **kw: captured.append(kw)))
    sink.record(OnboardingEvent('company_question_answered', 2, 'voice', question_id='q1'))
    assert captured[0]['metadata'] == {'step': 2, 'input_mode': 'voice', 'question_id': 'q1'}
    with pytest.raises(ValueError):
        sink.record(OnboardingEvent('company_question_answered', 2, question_id='private narrative'))
