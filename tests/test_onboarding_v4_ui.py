import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from models.candidate import Candidate
from models.candidate_onboarding import CandidateOnboarding
from models.company_interview import V4_VERSION
from services.candidate_repository import CandidateRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository


APP = """
import json
import streamlit as st
from types import SimpleNamespace
from components.onboarding import render_onboarding
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from models.company_interview import V4_ADAPTIVE_QUESTIONS
class Gateway:
    def create_initial_profile(self, **kwargs):
        raise AssertionError("Profile generation is forbidden")
class Coverage:
    def generate(self, prompt):
        return json.dumps(dict(coverage=dict.fromkeys(V4_ADAPTIVE_QUESTIONS, "SUFFICIENT"), next_missing_dimension=None))
st.session_state.setdefault("events", [])
u = SimpleNamespace(id="u", candidate_id="a", access_level="candidate")
inputs = SimpleNamespace(config=SimpleNamespace(onboarding_enabled=False), events=None,
    event=lambda name, **kwargs: st.session_state["events"].append(name))
render_onboarding(candidate_id="a", candidate_name="Synthetic",
    onboarding_repository=CandidateOnboardingRepository(), profile_gateway=Gateway(),
    authenticated_user=u, active_user=u, voice_inputs=inputs, reflection_provider=Coverage())
"""


@pytest.fixture
def repo():
    for cid in ("a", "b"):
        CandidateRepository().save(Candidate(cid, "Synthetic", "", "", ""))
    return CandidateOnboardingRepository()


def app():
    result = AppTest.from_string(APP, default_timeout=20).run()
    assert not result.exception
    return result


def widget(at, kind, label):
    return next(item for item in getattr(at, kind) if item.label == label)


def click(at, label):
    widget(at, "button", label).click().run()
    assert not at.exception


def about(at):
    widget(at, "selectbox", "Country").set_value("Ireland").run()
    widget(at, "text_input", "City").set_value(" Dublin ")
    at.multiselect[0].set_value(["English"])
    click(at, "Continue")


def seed(repo):
    data = CandidateOnboarding("a", country="Ireland", city="Dublin", spoken_languages=["English"],
        location="Legacy", work_authorisation="Legacy authorization", desired_next_work="Legacy direction",
        enjoyed_work="Enjoyed", avoid_work="Avoid", development_interests="Develop",
        career_priorities=["Legacy priority"], priority_declaration="Existing declaration")
    repo.save_onboarding(data)
    repo.add_work_experience("a", "Company", "2020-01", None, "Story", "Source", role="Analyst")
    return data


def start_company(at, role="Analyst", current=True):
    widget(at, "text_input", "Company").set_value(" Company ")
    widget(at, "text_input", "Role").set_value(role)
    widget(at, "selectbox", "Start month").set_value(1)
    widget(at, "selectbox", "Start year").set_value(2020)
    widget(at, "checkbox", "I currently work here").set_value(current)
    if not current:
        widget(at, "selectbox", "End month").set_value(1)
        widget(at, "selectbox", "End year").set_value(2019)
    click(at, "Start company interview")


def test_interview_reruns_do_not_reload_about_or_completed_experiences(repo, monkeypatch):
    at = app()
    about(at)
    start_company(at)
    def forbidden(*args, **kwargs):
        raise AssertionError("Unrelated onboarding reads during active interview")
    monkeypatch.setattr(CandidateOnboardingRepository, "get_onboarding", forbidden)
    monkeypatch.setattr(CandidateOnboardingRepository, "list_work_experiences", forbidden)
    for index in range(3):
        at.text_area[0].set_value(f"Confirmed source {index}")
        click(at, "Save & continue")
    at.run()
    assert not at.exception


def test_full_journey_collects_raw_only_and_never_duplicates_experience(repo):
    at = app()
    assert not at.text_input
    assert [s.label for s in at.selectbox] == ["Country"]
    about(at)
    click(at, "Continue")
    assert at.warning and at.session_state["onboarding_step_a"] == 2
    start_company(at)
    draft = repo.get_company_draft("a")
    assert draft["role"] == "Analyst" and draft["end_date"] is None
    assert draft["onboarding_interview_version"] == V4_VERSION
    for index in range(3):
        at.text_area[0].set_value(f"Source {index}")
        click(at, "Save & continue")
    click(at, "Check for missing information")
    click(at, "Looks right")
    assert len(repo.list_work_experiences("a")) == 1
    at.run()
    assert len(repo.list_work_experiences("a")) == 1
    click(at, "Continue")
    assert at.subheader[0].value == "Education"
    click(at, "Continue")
    assert at.subheader[0].value == "Certifications"
    click(at, "Continue")
    assert at.subheader[0].value == "Priorities" and len(at.multiselect) == 0
    click(at, "I'll add these later")
    assert at.session_state["onboarding_step_a"] == 6
    assert repo.get_onboarding("a").priority_declaration == ""
    assert "ready for profile construction" in at.success[0].value
    assert not {"onboarding_completed", "candidate_profile_created"} & set(at.session_state["events"])
    assert all("Profile" not in button.label for button in at.button)
    click(at, "Back")
    click(at, "Back")
    assert len(repo.list_work_experiences("a")) == 1


def test_about_preserves_arbitrary_languages_and_unrelated_fields(repo):
    original = seed(repo)
    original = replace(original, spoken_languages=["English", "Irish Sign Language"])
    repo.save_onboarding(original)
    at = app()
    at.session_state["onboarding_step_a"] = 1
    at.run()
    assert at.multiselect[0].value == original.spoken_languages
    assert not any("author" in item.label.lower() for item in at.text_input)
    widget(at, "text_input", "City").set_value(" Cork ")
    at.multiselect[0].set_value(["Irish Sign Language", "New declared language"])
    click(at, "Continue")
    assert repo.get_onboarding("a") == replace(original, city="Cork",
        spoken_languages=["Irish Sign Language", "New declared language"])
    click(at, "Back")
    assert at.multiselect[0].value == ["Irish Sign Language", "New declared language"]


@pytest.mark.parametrize("role,current", [("", True), ("Analyst", False)])
def test_experience_invalid_role_or_reversed_dates_rejected(repo, role, current):
    at = app()
    about(at)
    start_company(at, role, current)
    assert at.warning
    assert repo.get_company_draft("a") is None


def test_education_and_certification_add_list_remove_are_scoped(repo):
    seed(repo)
    other = repo.add_education(candidate_id="b", institution="Other", qualification="Other", field="Other")
    other_cert = repo.add_certification(candidate_id="b", name="Other", issuer="Other", year_obtained=2020)
    at = app()
    assert {item.label for item in at.text_input} == {"Institution", "Field"}
    assert [item.label for item in at.selectbox] == ["Qualification"]
    assert not at.date_input and not at.number_input and not at.get("audio_input")
    for _ in range(2):
        widget(at, "selectbox", "Qualification").set_value("Other").run()
        for label, value in [("Institution", "School"), ("Other qualification", "Custom qualification"), ("Field", "Data")]:
            widget(at, "text_input", label).set_value(value)
        click(at, "Add education")
    assert len(repo.list_education("a")) == 2
    click(at, "Remove")
    assert len(repo.list_education("a")) == 1
    assert repo.list_education("b") == [other]
    click(at, "Continue")
    assert {item.label for item in at.text_input} == {"Certification name", "Issuer"}
    assert [item.label for item in at.number_input] == ["Year obtained"]
    assert not at.date_input and not at.get("audio_input")
    for _ in range(2):
        widget(at, "text_input", "Certification name").set_value("Certificate")
        widget(at, "text_input", "Issuer").set_value("Issuer")
        at.number_input[0].set_value(2021)
        click(at, "Add certification")
    assert len(repo.list_certifications("a")) == 2
    click(at, "Remove")
    assert len(repo.list_certifications("a")) == 1
    assert repo.list_certifications("b") == [other_cert]


@pytest.mark.parametrize("choice,custom,expected", [
    (None, None, None),
    ("Other", "   ", None),
    ("Bachelor's degree", None, "Bachelor's degree"),
    ("Other", "  Explicit custom qualification  ", "Explicit custom qualification"),
])
def test_education_qualification_is_explicit_and_validated(repo, monkeypatch, choice, custom, expected):
    seed(repo)
    save = Mock(wraps=repo.add_education)
    monkeypatch.setattr(CandidateOnboardingRepository, "add_education", save)
    at = app()
    assert widget(at, "selectbox", "Qualification").value is None
    if choice is not None:
        widget(at, "selectbox", "Qualification").set_value(choice).run()
    widget(at, "text_input", "Institution").set_value("School")
    widget(at, "text_input", "Field").set_value("Data")
    if custom is not None:
        widget(at, "text_input", "Other qualification").set_value(custom)
    else:
        assert "Other qualification" not in [item.label for item in at.text_input]
    click(at, "Add education")
    if expected is None:
        assert at.warning
        save.assert_not_called()
        assert not repo.list_education("a")
    else:
        save.assert_called_once_with(candidate_id="a", institution="School",
                                    qualification=expected, field="Data")
        assert [record.qualification for record in repo.list_education("a")] == [expected]


def test_priorities_save_skip_and_back_preserve_about_and_legacy(repo):
    original = seed(repo)
    at = app()
    click(at, "Continue")
    click(at, "Continue")
    assert len(at.text_area) == 1 and not at.multiselect and not at.get("audio_input")
    assert at.text_area[0].value == "Existing declaration"
    click(at, "Back")
    click(at, "Continue")
    click(at, "I'll add these later")
    assert repo.get_onboarding("a") == original
    click(at, "Back")
    at.text_area[0].set_value("  Remote, no weekends.  ")
    click(at, "Continue")
    assert repo.get_onboarding("a") == replace(original, priority_declaration="Remote, no weekends.")


def test_new_session_resume_is_conservative_and_current_session_later_step_survives(repo):
    seed(repo)
    at = app()
    assert at.session_state["onboarding_step_a"] == 3
    at.session_state["onboarding_step_a"] = 6
    at.run()
    assert at.session_state["onboarding_step_a"] == 6
    fresh = app()
    assert fresh.session_state["onboarding_step_a"] == 3


def test_durable_interview_takes_priority_over_missing_about(repo):
    repo.begin_company_interview(candidate_id="a", company="Company", role="Analyst",
        start_date="2020-01", end_date=None, experience_id="draft", interview_version=V4_VERSION)
    at = app()
    assert at.session_state["onboarding_step_a"] == 2
    assert len(at.text_area) == 1
    at.text_area[0].set_value("Source")
    click(at, "Save & continue")
    fresh = app()
    assert fresh.session_state["onboarding_step_a"] == 2
    assert any("problems" in m.value for m in fresh.markdown)
    assert len(repo.get_company_draft("a")["answers"]) == 1


@pytest.mark.parametrize("actor_candidate,active_candidate", [("b", "a"), ("a", "b")])
def test_access_denial_happens_before_storage(actor_candidate, active_candidate, monkeypatch):
    import components.onboarding as module
    ui, repo = Mock(), Mock()
    monkeypatch.setattr(module, "st", ui)
    module.render_onboarding(candidate_id="a", candidate_name="Synthetic",
        onboarding_repository=repo, profile_gateway=Mock(),
        authenticated_user=SimpleNamespace(id="actor", candidate_id=actor_candidate, access_level="candidate"),
        active_user=SimpleNamespace(id="active", candidate_id=active_candidate))
    ui.error.assert_called_once_with("Access denied.")
    assert not repo.mock_calls


@pytest.mark.parametrize("step", range(1, 7))
def test_stepper_and_side_panel_are_five_source_steps(step, monkeypatch):
    import components.onboarding as module
    ui = Mock()
    monkeypatch.setattr(module, "st", ui)
    module._render_workpilot_stepper(step)
    module._render_workpilot_side_panel(step)
    for args in ui.html.call_args_list:
        html = args.args[0]
        for name in ("About You", "Experience", "Education", "Certifications", "Priorities"):
            assert name in html
        assert "Build profile" not in html and "Your direction" not in html
    if step == 6:
        assert ui.html.call_args_list[0].args[0].count('class="wp-step-item done"') == 5
        assert ui.html.call_args_list[1].args[0].count('class="wp-side-step done"') == 5


def test_no_profile_or_interpretation_authority_and_static_countries():
    from components.country_names import COUNTRY_NAMES
    assert len(COUNTRY_NAMES) == len(set(COUNTRY_NAMES)) == 249
    source = Path("components/onboarding.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"create_initial_profile", "interpret", "generate", "update_profile", "add_work_experience"}
    for legacy in ("PRIORITY_OPTIONS", "desired_next_work", "work_authorisation", "enjoyed_work", "avoid_work",
                   "development_interests", "career_priorities", "onboarding_completed", "candidate_profile_created"):
        assert legacy not in source
