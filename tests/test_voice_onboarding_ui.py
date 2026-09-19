from streamlit.testing.v1 import AppTest

APP = '''
import streamlit as st
from types import SimpleNamespace
from components.profile_onboarding import render_profile_onboarding
from components.voice_text_input import VoiceTextInputs, bind_scope
from models.app_user import AppUser
from services.ai.voice_transcription import VoiceConfig
from tests.company_interview_fakes import FakeReflection

class Repo:
    def get_onboarding(self, candidate_id): return st.session_state.get('saved_onboarding')
    def list_work_experiences(self, candidate_id): return st.session_state.get('saved_experiences', [])
    def save_onboarding(self, item): st.session_state.saved_onboarding = item
    def add_work_experience(self, **kw):
        item = SimpleNamespace(id='exp', **kw)
        st.session_state.saved_experiences = [*self.list_work_experiences('c'), item]
    def delete_work_experience(self, *a, **kw): pass
    def confirm_company_interview(self, **kw):
        from models.company_interview import validate_answers
        validate_answers(kw['answers'])
        self.add_work_experience(candidate_id=kw['candidate_id'], company=kw['company'],
            start_date=kw['start_date'], end_date=kw['end_date'], career_story='',
            day_to_day_narrative=' '.join(a.confirmed_text for a in kw['answers']))
class Generator:
    def generate(self, **kw): st.session_state.generated = True
u = AppUser('u','private@example.test','Private', 'c')
scope = bind_scope(st.session_state, 'u','u','c')
inputs = VoiceTextInputs(scope, config=VoiceConfig(), provider=object(), events=None)
if not st.session_state.get('generated'):
    render_profile_onboarding(candidate_id='c', candidate_name='Private', onboarding_repository=Repo(),
        profile_generation_service=Generator(), authenticated_user=u, active_user=u, voice_inputs=inputs,
        reflection_provider=FakeReflection())
'''


def button(at, label):
    return next(b for b in at.button if b.label == label)


def test_entire_text_onboarding_reruns_back_review_and_generation():
    at = AppTest.from_string(APP, default_timeout=15).run()
    assert not at.exception
    at.text_input[0].set_value('Ireland')
    at.multiselect[0].set_value(['English'])
    button(at,'Continue →').click().run()
    assert not at.exception
    assert len(at.text_area) == 0
    at.text_input[0].set_value('Synthetic Co')
    at.selectbox[0].set_value(1)
    at.selectbox[1].set_value(2020)
    at.checkbox[0].check()
    button(at,'Start company interview').click().run()
    for i in range(8):
        assert len(at.text_area) == 1
        at.text_area[0].set_value('Helped customers ' + str(i))
        button(at,'Continue').click().run()
    button(at,"Show me what you've got").click().run()
    button(at,'Continue').click().run()
    button(at,'skip').click().run()
    button(at,'This looks right').click().run()
    assert not at.exception
    assert at.session_state['saved_experiences'][0].career_story == ''
    button(at,'Continue →').click().run()
    assert not at.exception and len(at.text_area) == 4
    at.text_area[0].set_value('Support work')
    at.text_area[1].set_value('Helping people')
    button(at,'Back').click().run()
    button(at,'Continue →').click().run()
    assert at.text_area[0].value == 'Support work'
    button(at,'Review profile →').click().run()
    assert not at.exception
    assert at.session_state['saved_onboarding'].desired_next_work == 'Support work'
    button(at,'Build my Career Profile').click().run()
    assert not at.exception and at.session_state['generated'] is True


def test_component_rejects_foreign_candidate():
    app = APP.replace("candidate_id='c', candidate_name", "candidate_id='foreign', candidate_name")
    at = AppTest.from_string(app).run()
    assert not at.exception and at.error[0].value == 'Access denied.'


def test_pending_transcript_blocks_save_until_explicit_acceptance():
    at = AppTest.from_string(APP, default_timeout=15).run()
    at.text_input[0].set_value('Ireland')
    at.multiselect[0].set_value(['English'])
    button(at,'Continue →').click().run()
    at.text_input[0].set_value('Synthetic Co')
    at.selectbox[0].set_value(1)
    at.selectbox[1].set_value(2020)
    at.checkbox[0].check()
    button(at,'Start company interview').click().run()
    at.text_area[0].set_value('Original typed answer')
    button(at,'Continue').click().run()
    for _ in range(7):
        button(at,'skip').click().run()
    assert 'saved_experiences' not in at.session_state
    button(at,"Show me what you've got").click().run()
    button(at,'Continue').click().run()
    button(at,'skip').click().run()
    assert 'saved_experiences' not in at.session_state
    at.text_area[0].set_value('User corrected Portuguese answer')
    button(at,'This looks right').click().run()
    assert not at.exception
    saved = at.session_state['saved_experiences'][0]
    assert saved.day_to_day_narrative.strip() == 'User corrected Portuguese answer'


def test_v2_reflection_correction_adaptive_final_and_editable_sources():
    from models.company_interview import QUESTIONS, FINAL_QUESTION, ADAPTIVE_QUESTIONS
    at = AppTest.from_string(APP.replace('reflection_provider=FakeReflection()',
        "reflection_provider=FakeReflection('concrete_evidence')"), default_timeout=15).run()
    at.text_input[0].set_value('Ireland')
    at.multiselect[0].set_value(['English'])
    button(at, 'Continue →').click().run()
    at.text_input[0].set_value('Synthetic Operations Co')
    at.selectbox[0].set_value(1)
    at.selectbox[1].set_value(2020)
    at.checkbox[0].check()
    button(at, 'Start company interview').click().run()
    for index, question in enumerate(QUESTIONS):
        visible = [m.value for m in at.markdown]
        assert question in visible
        assert not any(q in visible for q in QUESTIONS[index + 1:])
        assert any('Core conversation:' in c.value for c in at.caption)
        assert len(at.text_area) == 1
        at.text_area[0].set_value('Concrete source ' + str(index))
        button(at, 'Continue').click().run()
    button(at, "Show me what you've got").click().run()
    assert "What I've got so far" in [m.value for m in at.markdown]
    at.text_area[0].set_value("It's BPO, not PPO.")
    button(at, 'Continue').click().run()
    assert ADAPTIVE_QUESTIONS['concrete_evidence'] in [m.value for m in at.markdown]
    assert FINAL_QUESTION not in [m.value for m in at.markdown]
    at.text_area[0].set_value('I checked logs during that incident.')
    button(at, 'Continue').click().run()
    assert FINAL_QUESTION in [m.value for m in at.markdown]
    at.text_area[0].set_value('A final forgotten detail.')
    button(at, 'Continue').click().run()
    assert len(at.text_area) == 11
    assert 'saved_experiences' not in at.session_state
    at.text_area[0].set_value('User corrected source zero')
    button(at, 'This looks right').click().run()
    assert not at.exception
    saved = at.session_state['saved_experiences'][0].day_to_day_narrative
    assert "It's BPO, not PPO." in saved and 'A final forgotten detail.' in saved
    assert 'User corrected source zero' in saved and 'Concrete source 0' not in saved
