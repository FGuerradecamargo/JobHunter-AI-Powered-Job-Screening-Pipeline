from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest
from streamlit.testing.v1 import AppTest

from components import company_interview as component
from models.company_interview import V1_VERSION, V2_VERSION, V3_VERSION, V4_VERSION, V4_QUESTIONS, V4_ADAPTIVE_QUESTIONS
from services.company_interview import start_interview
from tests.test_company_interview_v4 import repo


class Rerun(BaseException):
    pass


class UI:
    def __init__(self, draft):
        self.session_state = {"_voice_owner": "scope", "_voice_company_draft_scope": draft}
        self.clicked = None
        self.text = ""
        self.recording = None
        self.shown = []
        self.buttons = []
        self.progresses = []

    def write(self, text): self.shown.append(text)
    caption = subheader = warning = error = success = write
    def progress(self, value): self.progresses.append(value)
    def spinner(self, text): return nullcontext()
    def text_area(self, label, **kwargs): return self.text or kwargs.get("value", "")
    def audio_input(self, *args, **kwargs): return self.recording
    def button(self, label, **kwargs):
        self.buttons.append(label)
        return label == self.clicked and not kwargs.get("disabled", False)
    def rerun(self): raise Rerun()


def setup_ui(repo, voice=False):
    draft = start_interview("scope", "a", "Synthetic", "2020-01", None,
        role="Analyst", version=V4_VERSION, repository=repo)
    inputs = SimpleNamespace(config=SimpleNamespace(onboarding_enabled=voice,
        transcription_enabled=True, model="fake"), provider=Mock(), events=None)
    return draft, UI(draft), inputs


def render(draft, ui, inputs, repo, provider=None, click=None, text=""):
    ui.clicked, ui.text = click, text
    ui.shown, ui.buttons = [], []
    try:
        component.render_company_interview(draft, "scope", repo, inputs, ui, provider)
    except Rerun:
        pass


def coverage(dimension=None):
    statuses = dict.fromkeys(V4_ADAPTIVE_QUESTIONS, "SUFFICIENT")
    if dimension:
        statuses[dimension] = "INSUFFICIENT"
    return json.dumps(dict(coverage=statuses, next_missing_dimension=dimension))


@pytest.mark.parametrize("version", [V1_VERSION, V2_VERSION, V3_VERSION, V4_VERSION])
def test_explicit_dispatch(version, monkeypatch):
    draft = dict(scope="scope", version=version, id="test", answers=[], stage="memory")
    ui = UI(draft)
    v3, v4 = Mock(), Mock()
    monkeypatch.setattr(component, "render_v3_company_interview", v3)
    monkeypatch.setattr(component, "render_v4_company_interview", v4)
    if version in (V1_VERSION, V2_VERSION):
        monkeypatch.setattr(component, "current_question", lambda _: ("q1", "Legacy question", "FIXED_QUESTION"))
    component.render_company_interview(draft, "scope", Mock(),
        SimpleNamespace(config=SimpleNamespace(onboarding_enabled=False), events=None), ui)
    assert v4.call_count == (1 if version == V4_VERSION else 0)
    assert v3.call_count == (1 if version == V3_VERSION else 0)
    if version in (V1_VERSION, V2_VERSION):
        assert "Legacy question" in ui.shown


@pytest.mark.parametrize("followups", [[], ["tools_resources"], ["tools_resources", "core_work"]])
def test_full_ui_flow_delegates_to_services(repo, monkeypatch, followups):
    draft, ui, inputs = setup_ui(repo)
    spies = {}
    for name in ("confirm_text", "skip_question", "reflect_v4", "save_correction", "finalize"):
        spy = Mock(wraps=getattr(component, name))
        monkeypatch.setattr(component, name, spy)
        spies[name] = spy
    monkeypatch.setattr(component, "reflect_v3", Mock(side_effect=AssertionError("V3 reflection")))
    monkeypatch.setattr(component, "set_adaptive_dimensions", Mock(side_effect=AssertionError("UI dimension selection")))
    provider = Mock()
    for i, question in enumerate(V4_QUESTIONS):
        render(draft, ui, inputs, repo)
        assert question in ui.shown
        assert f"Core conversation: {i+1} / 3" in ui.shown
        render(draft, ui, inputs, repo, click="skip" if i == 1 else "Save & continue", text=f"Source {i}")
    assert spies["confirm_text"].call_count == 2
    assert spies["skip_question"].call_count == 1
    assert draft["stage"] == "reflection_pending"
    provider.generate.assert_not_called()
    for dimension in followups:
        provider.generate.return_value = coverage(dimension)
        render(draft, ui, inputs, repo, provider, click="Check for missing information")
        render(draft, ui, inputs, repo, provider)
        assert "A quick follow-up" in ui.shown
        assert V4_ADAPTIVE_QUESTIONS[dimension] in ui.shown
        assert ui.progresses[-1] == 1
        render(draft, ui, inputs, repo, provider, click="Save & continue", text="Adaptive source")
    if len(followups) < 2:
        assert draft["stage"] == "reflection_pending"
        provider.generate.return_value = coverage()
        render(draft, ui, inputs, repo, provider, click="Check for missing information")
    assert draft["stage"] == "review"
    assert provider.generate.call_count == min(len(followups)+1, 2)
    if followups:
        second_request = json.loads(provider.generate.call_args.args[0].split("SOURCE DATA:\n")[1])
        assert any(a["source_kind"] == "ADAPTIVE_QUESTION" for a in second_request["sources"])
    draft["reflection"] = {"interpretation": {"summary": [{"text": "FORBIDDEN PROFILE CLAIM"}]}}
    render(draft, ui, inputs, repo)
    assert "Source 0" in ui.shown and "Not provided" in ui.shown
    assert "FORBIDDEN PROFILE CLAIM" not in str(ui.shown)
    assert "Check for missing information" not in ui.buttons
    render(draft, ui, inputs, repo, click="Save correction", text="My correction")
    spies["save_correction"].assert_called_once()
    prefix = "_voice_company_" + draft["id"] + "_"
    ui.session_state.update({prefix+"q1_text": "own", prefix[:-1]+"other_q1_text": "other",
        "_voice_company_draft_other": {"id": "other"}, "onboarding_step": 2})
    render(draft, ui, inputs, repo, click="Looks right")
    spies["finalize"].assert_called_once()
    assert draft["stage"] == "complete"
    assert "_voice_company_draft_scope" not in ui.session_state
    assert prefix+"q1_text" not in ui.session_state
    assert ui.session_state[prefix[:-1]+"other_q1_text"] == "other"
    assert ui.session_state["onboarding_step"] == 2
    assert ui.session_state["_voice_owner"] == "scope"
    assert "_voice_company_draft_other" in ui.session_state
    assert len(repo.list_work_experiences("a")) == 1


def test_coverage_failure_is_retryable_without_source_or_stage_changes(repo):
    draft, ui, inputs = setup_ui(repo)
    for _ in range(3):
        render(draft, ui, inputs, repo, click="skip")
    original = list(draft["answers"])
    provider = Mock()
    provider.generate.side_effect = RuntimeError("PRIVATE PROVIDER ERROR")
    render(draft, ui, inputs, repo, provider, click="Check for missing information")
    render(draft, ui, inputs, repo, provider)
    assert draft["stage"] == "reflection_pending"
    assert draft["answers"] == original
    assert "Retry coverage check" in ui.buttons
    assert "PRIVATE PROVIDER ERROR" not in str(ui.shown)
    assert not any("Continue with" in label for label in ui.buttons)
    provider.generate.side_effect = None
    provider.generate.return_value = coverage()
    render(draft, ui, inputs, repo, provider, click="Retry coverage check")
    assert draft["stage"] == "review"
    assert draft["answers"] == original


def test_voice_review_discard_and_confirm_use_service_boundary(repo, monkeypatch):
    draft, ui, inputs = setup_ui(repo, voice=True)
    monkeypatch.setattr("services.company_interview.audio_duration", lambda _: 1)
    inputs.provider.transcribe.return_value = SimpleNamespace(status="succeeded", transcript_text="Unconfirmed")
    spies = {}
    for name in ("transcribe_voice", "discard_voice", "confirm_voice_transcript"):
        spies[name] = Mock(wraps=getattr(component, name))
        monkeypatch.setattr(component, name, spies[name])
    ui.recording = SimpleNamespace(getvalue=lambda: b"fake")
    render(draft, ui, inputs, repo, click="Continue with recording")
    assert draft["stage"] == "voice_review"
    assert repo.list_company_answers("a", draft["id"]) == []
    prefix = "_voice_company_" + draft["id"] + "_q1"
    ui.session_state[prefix+"_audio"] = "old recording"
    render(draft, ui, inputs, repo, click="Record again")
    assert prefix+"_audio" not in ui.session_state
    assert draft["stage"] == "question"
    assert repo.list_company_answers("a", draft["id"]) == []
    render(draft, ui, inputs, repo, click="Continue with recording")
    render(draft, ui, inputs, repo, click="Save & continue", text="Candidate edited transcript")
    assert spies["transcribe_voice"].call_count == 2
    spies["discard_voice"].assert_called_once()
    spies["confirm_voice_transcript"].assert_called_once()
    assert repo.list_company_answers("a", draft["id"])[0].confirmed_text == "Candidate edited transcript"


def test_direct_v4_renderer_rejects_other_versions():
    draft = dict(scope="scope", version=V3_VERSION)
    with pytest.raises(ValueError):
        component.render_v4_company_interview(draft, "scope", Mock(), Mock(), UI(draft))


def test_failed_finalization_keeps_draft_and_source_answers(repo, monkeypatch):
    draft, ui, inputs = setup_ui(repo)
    for _ in range(3):
        render(draft, ui, inputs, repo, click="skip")
    provider = Mock()
    provider.generate.return_value = coverage()
    render(draft, ui, inputs, repo, provider, click="Check for missing information")
    monkeypatch.setattr(component, "finalize", Mock(side_effect=RuntimeError("PRIVATE DB ERROR")))
    render(draft, ui, inputs, repo, click="Looks right")
    assert draft["stage"] == "review"
    assert ui.session_state["_voice_company_draft_scope"] is draft
    assert len(repo.get_company_draft("a")["answers"]) == 3
    assert "PRIVATE DB ERROR" not in str(ui.shown)


def test_voice_to_typed_answer_switch(repo):
    draft, ui, inputs = setup_ui(repo, voice=True)
    render(draft, ui, inputs, repo, click="type instead")
    assert draft["typing"] is True
    render(draft, ui, inputs, repo, click="Save & continue", text="Typed source")
    assert repo.list_company_answers("a", draft["id"])[0].confirmed_text == "Typed source"


def test_complete_does_not_clear_another_active_draft(repo):
    draft, ui, inputs = setup_ui(repo)
    draft["stage"] = "complete"
    other = dict(id="other", candidate_id="a", version=V4_VERSION)
    ui.session_state["_voice_company_draft_scope"] = other
    render(draft, ui, inputs, repo)
    assert ui.session_state["_voice_company_draft_scope"] is other


def test_v4_streamlit_reruns_and_final_cleanup(repo):
    app = AppTest.from_string("""
import json
import streamlit as st
from types import SimpleNamespace
from components.company_interview import render_company_interview
from services.company_interview import start_interview
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from models.company_interview import V4_ADAPTIVE_QUESTIONS, V4_VERSION
class Provider:
    def generate(self, prompt):
        return json.dumps(dict(coverage=dict.fromkeys(V4_ADAPTIVE_QUESTIONS, "SUFFICIENT"), next_missing_dimension=None))
repo = CandidateOnboardingRepository()
st.session_state["_voice_owner"] = "scope"
if not repo.list_work_experiences("a"):
    if "_voice_company_draft_scope" not in st.session_state:
        st.session_state["_voice_company_draft_scope"] = start_interview(
            "scope", "a", "Synthetic", "2020-01", None, role="Analyst", version=V4_VERSION, repository=repo)
    render_company_interview(st.session_state["_voice_company_draft_scope"], "scope", repo,
        SimpleNamespace(config=SimpleNamespace(onboarding_enabled=False)), reflection_provider=Provider())
else:
    st.success("Confirmed")
""").run()
    for label in ["skip", "skip", "skip", "Check for missing information", "Looks right"]:
        next(b for b in app.button if b.label == label).click().run()
        assert not app.exception
    assert "_voice_company_draft_scope" not in app.session_state
    assert app.success[0].value == "Confirmed"
