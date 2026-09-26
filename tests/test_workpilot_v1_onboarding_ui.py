from unittest.mock import Mock
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest
from models.candidate import Candidate
from models.company_interview import V3_VERSION, V3_QUESTIONS
from services.candidate_repository import CandidateRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from services.company_interview import (
    start_interview, resume_interview, confirm_text, confirm_voice_transcript,
    transcribe_voice, set_adaptive_dimensions, save_correction, finalize,
)

APP = '''
import streamlit as st
from types import SimpleNamespace
from components.company_interview import render_company_interview
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from services.company_interview import start_interview, resume_interview
from services.ai.voice_transcription import VoiceConfig
repo = CandidateOnboardingRepository()
scope = 'test-browser'
st.session_state['_voice_owner'] = scope
if not repo.list_work_experiences('a'):
    key = '_voice_company_draft_' + scope
    if key not in st.session_state:
        st.session_state[key] = resume_interview(scope, 'a', repo) or start_interview(
            scope, 'a', 'Synthetic', '2020-01', None, repository=repo, version='company-interview-v3')
    render_company_interview(st.session_state[key], scope, repo,
        SimpleNamespace(config=VoiceConfig(), provider=object(), events=None))
else:
    st.success('Confirmed')
'''


@pytest.fixture
def setup():
    CandidateRepository().save(Candidate('a', 'Synthetic', '', '', ''))
    repo = CandidateOnboardingRepository()
    return repo


def click(app, label):
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception


def test_v3_ui_persists_each_answer_recovers_new_session_and_finalizes(setup):
    repo = setup
    app = AppTest.from_string(APP).run()
    assert not app.exception
    app.text_area[0].set_value('First source answer')
    click(app, 'Save & continue')
    assert len(repo.get_company_draft('a')['answers']) == 1
    assert repo.list_work_experiences('a') == []
    # A new AppTest has no old browser state, but sees the same durable database.
    app = AppTest.from_string(APP).run()
    assert not app.exception
    assert any(V3_QUESTIONS[1] in m.value for m in app.markdown)
    for _ in range(3):
        click(app, 'skip')
    assert repo.get_company_draft('a') is not None
    click(app, 'Review this experience')
    click(app, 'Looks right')
    experiences = repo.list_work_experiences('a')
    assert len(experiences) == 1
    assert 'First source answer' in experiences[0].day_to_day_narrative
    assert repo.get_company_draft('a') is None


def test_voice_save_failure_keeps_pending_review_and_no_evidence(setup, monkeypatch):
    repo = setup
    draft = start_interview('scope', 'a', 'Synthetic', '2020', None, repository=repo, version=V3_VERSION)
    monkeypatch.setattr('services.company_interview.audio_duration', lambda _: 1)
    provider = Mock()
    provider.transcribe.return_value = SimpleNamespace(status='succeeded', transcript_text='Unconfirmed')
    transcribe_voice(draft, 'scope', b'fixture', provider,
        SimpleNamespace(transcription_enabled=True, model='fake'), authorized=True)
    assert repo.list_company_answers('a', draft['id']) == []
    broken = Mock()
    broken.save_company_answer.side_effect = RuntimeError('Synthetic failure')
    with pytest.raises(RuntimeError):
        confirm_voice_transcript(draft, 'scope', broken, 'User checked text')
    assert draft['stage'] == 'voice_review'
    assert draft['pending_voice'] is not None
    confirm_voice_transcript(draft, 'scope', repo, 'User checked text')
    assert repo.list_company_answers('a', draft['id'])[0].confirmed_text == 'User checked text'


def test_stale_review_cannot_finalize_unseen_correction(setup):
    repo = setup
    draft = start_interview('scope', 'a', 'Synthetic', '2020', None, repository=repo, version=V3_VERSION)
    for _ in range(4):
        confirm_text(draft, 'scope', repo, 'Source')
    set_adaptive_dimensions(draft, 'scope', [])
    other = resume_interview('other', 'a', repo)
    set_adaptive_dimensions(other, 'other', [])
    save_correction(other, 'other', repo, 'My correction')
    with pytest.raises(ValueError, match='changed'):
        finalize(draft, 'scope', repo)
    assert repo.get_company_draft('a') is not None
    finalize(other, 'other', repo)
    assert len(repo.list_work_experiences('a')) == 1


def test_reflection_two_followups_and_derived_text_never_replace_sources(setup):
    import json
    from models.company_interview import ADAPTIVE_QUESTIONS
    from services.company_reflection import reflect_v3, FIELDS
    repo = setup
    draft = start_interview('scope', 'a', 'Synthetic', '2020', None, repository=repo, version=V3_VERSION)
    for _ in range(4):
        confirm_text(draft, 'scope', repo, 'Exact source text')
    payload = dict(interpretation={field: [] for field in FIELDS},
        coverage={dimension: 'INSUFFICIENT' for dimension in ADAPTIVE_QUESTIONS},
        material_missing_dimensions=['context', 'stakeholders'])
    payload['interpretation']['summary'] = [dict(text='Derived reflection only',
        support=[dict(question_id='q1', quote='Exact source text')], uncertainty='Draft')]
    provider = Mock()
    provider.generate.return_value = json.dumps(payload)
    reflection = reflect_v3(draft, 'scope', provider, authorized=True)
    set_adaptive_dimensions(draft, 'scope', reflection['material_missing_dimensions'])
    for _ in range(2):
        confirm_text(draft, 'scope', repo, 'More source')
    assert draft['stage'] == 'review'
    restored = resume_interview('scope', 'a', repo)
    assert restored['stage'] == 'review'
    finalize(restored, 'scope', repo)
    experience = repo.list_work_experiences('a')[0]
    assert 'Derived reflection only' not in experience.day_to_day_narrative
    assert len(experience.confirmed_interview_answers) == 6


def test_scope_rejects_foreign_confirmation_without_write(setup):
    draft = start_interview('owner', 'a', 'Synthetic', '2020', None, repository=setup, version=V3_VERSION)
    with pytest.raises(ValueError):
        confirm_text(draft, 'other', setup, 'Foreign answer')
    assert setup.list_company_answers('a', draft['id']) == []
