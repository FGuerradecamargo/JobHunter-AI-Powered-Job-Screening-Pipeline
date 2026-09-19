from streamlit.testing.v1 import AppTest

APP = '''
import streamlit as st
from types import SimpleNamespace
from components.profile_onboarding import render_profile_onboarding
from components.voice_text_input import VoiceTextInputs, bind_scope
from models.app_user import AppUser
from services.ai.voice_transcription import VoiceConfig

class Repo:
    def get_onboarding(self, candidate_id): return st.session_state.get('saved_onboarding')
    def list_work_experiences(self, candidate_id): return st.session_state.get('saved_experiences', [])
    def save_onboarding(self, item): st.session_state.saved_onboarding = item
    def add_work_experience(self, **kw):
        item = SimpleNamespace(id='exp', **kw)
        st.session_state.saved_experiences = [*self.list_work_experiences('c'), item]
    def delete_work_experience(self, *a, **kw): pass
class Generator:
    def generate(self, **kw): st.session_state.generated = True
u = AppUser('u','private@example.test','Private', 'c')
scope = bind_scope(st.session_state, 'u','u','c')
inputs = VoiceTextInputs(scope, config=VoiceConfig(), provider=object(), events=None)
if not st.session_state.get('generated'):
    render_profile_onboarding(candidate_id='c', candidate_name='Private', onboarding_repository=Repo(),
        profile_generation_service=Generator(), authenticated_user=u, active_user=u, voice_inputs=inputs)
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
    assert len(at.text_area) == 2
    at.text_input[0].set_value('Synthetic Co')
    at.selectbox[0].set_value(1)
    at.selectbox[1].set_value(2020)
    at.checkbox[0].check()
    at.text_area[0].set_value('Original story')
    at.text_area[1].set_value('Helped customers')
    at.run()
    assert not at.exception
    assert at.text_area[0].value == 'Original story'
    button(at,'Add this experience').click().run()
    assert not at.exception
    assert at.session_state['saved_experiences'][0].career_story == 'Original story'
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
    scope = at.session_state['_voice_owner']
    draft_key = '_voice_draft_' + scope + '_career_story'
    at.session_state[draft_key]['pending'] = True
    at.text_area[0].set_value('machine transcript').run()
    assert button(at,'Add this experience').disabled
    assert 'saved_experiences' not in at.session_state
    at.text_area[0].set_value('User corrected Portuguese answer')
    button(at,'Accept answer').click().run()
    assert not button(at,'Add this experience').disabled
    at.text_input[0].set_value('Synthetic Co')
    at.selectbox[0].set_value(1)
    at.selectbox[1].set_value(2020)
    at.checkbox[0].check()
    at.text_area[1].set_value('Daily work')
    button(at,'Add this experience').click().run()
    assert not at.exception
    saved = at.session_state['saved_experiences'][0]
    assert saved.career_story == 'User corrected Portuguese answer'
    assert 'machine transcript' not in repr(saved)
