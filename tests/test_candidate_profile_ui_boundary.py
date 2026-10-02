import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from services import candidate_profile_runtime as runtime
from services.candidate_profile_priority_service import CandidateProfilePriorityService
from models.candidate import Candidate


def test_profile_page_is_orchestration_light():
    source = Path("pages/3_Profile.py").read_text(encoding="utf-8")
    for forbidden in ("ProfileReadinessService", "profile_readiness", "ProfileInterpretationService",
                      "ProfileSnapshotRepository", "CandidateProfileGenerationService", "OpenAIClient"):
        assert forbidden not in source
    assert "candidate_profile_service.refresh_current(candidate_id)" in source
    assert "render_profile_snapshot(candidate_profile_service.current(candidate_id))" in source
    assert "render_profile_snapshot(current_profile)" in source
    assert "profile_gateway=profile_runtime.onboarding_gateway" in source
    assert "elif current_profile is None:" in source
    assert "profile_exists = (\n            current_profile is not None" in source


def test_renderer_receives_data_not_persistence_key():
    source = Path("components/workpilot_ui.py").read_text(encoding="utf-8")
    assert "ProfileSnapshotRepository" not in source
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                and n.name == "render_profile_snapshot")
    assert [a.arg for a in node.args.args] == ["profile"]


def test_runtime_composes_shared_repositories_without_calling_ai(monkeypatch):
    snapshots, generation, readiness, service, gateway, priorities = (Mock() for _ in range(6))
    factories = []
    for name, value in (("ProfileSnapshotRepository", snapshots),
                        ("CandidateProfileGenerationService", generation),
                        ("ProfileReadinessService", readiness),
                        ("CandidateProfileService", service), ("CandidateProfileGateway", gateway),
                        ("CandidateProfilePriorityService", priorities)):
        factory = Mock(return_value=value)
        monkeypatch.setattr(runtime, name, factory)
        factories.append(factory)
    onboarding, updates, candidate = Mock(), Mock(), Mock()
    result = runtime.create_candidate_profile_runtime(onboarding_repository=onboarding,
        career_update_repository=updates, candidate_repository=candidate)
    assert result.service is service
    assert result.onboarding_gateway is gateway
    assert result.priorities is priorities
    kwargs = factories[1].call_args.kwargs
    assert kwargs["onboarding_repository"] is onboarding
    assert kwargs["career_update_repository"] is updates
    assert kwargs["candidate_repository"] is candidate
    assert kwargs["snapshot_repository"] is snapshots
    factories[2].assert_called_once_with(snapshots=snapshots, onboarding=onboarding, updates=updates)
    factories[3].assert_called_once_with(snapshot_repository=snapshots,
        readiness_service=readiness, generation_service=generation)
    factories[4].assert_called_once_with(generation)
    factories[5].assert_called_once_with(candidate)
    assert not generation.mock_calls
    assert not priorities.mock_calls


def test_profile_presentation_has_no_duplicate_canonical_candidate_reads():
    tree = ast.parse(Path("pages/3_Profile.py").read_text(encoding="utf-8"))
    reads = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
             and isinstance(node.value, ast.Name) and node.value.id == "generated_candidate"}
    assert not reads & {"proven_capabilities", "transferable_capabilities", "strengths",
                        "development_areas", "spoken_languages"}
    source = ast.unparse(tree)
    assert "generated_candidate" not in source
    assert "candidate_repository.get(" not in source
    for field in ("developing_capabilities", "technical_tools", "domain_experience",
                  "professional_experiences"):
        assert not any(isinstance(node, ast.Attribute) and node.attr == field for node in ast.walk(tree))
    composition = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name)
                       and node.func.id == "create_candidate_profile_runtime")
    assert any(kw.arg == "candidate_repository" and isinstance(kw.value, ast.Name)
               and kw.value.id == "candidate_repository" for kw in composition.keywords)
    assert "CandidatePriority" not in source
    assert "priority_candidate" not in source
    assert "candidate_repository.save(" not in source
    assert ".priorities.append(" not in source
    assert ".priorities.pop(" not in source
    for operation in ("list", "add", "update", "remove"):
        assert f"profile_runtime.priorities.{operation}(" in source
    assert not any(isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
                   and isinstance(node.value, ast.Attribute) and node.value.attr == "priorities"
                   for node in ast.walk(tree))


@pytest.mark.parametrize("candidate_exists", [True, False])
def test_current_priorities_ui_uses_service_for_crud(candidate_exists):
    tree = ast.parse(Path("pages/3_Profile.py").read_text(encoding="utf-8"))
    section = next(node for node in ast.walk(tree) if isinstance(node, ast.With)
                   and any(isinstance(item.context_expr, ast.Call)
                           and item.context_expr.args
                           and isinstance(item.context_expr.args[0], ast.Constant)
                           and item.context_expr.args[0].value == "Current priorities"
                           for item in node.items))
    repository = Mock()
    repository.get.return_value = (Candidate(id="a", name="Fixture", current_role="Support",
        current_level="Senior", professional_summary="Unchanged") if candidate_exists else None)
    repository.save.side_effect = lambda value: setattr(repository.get, "return_value", value)
    service = CandidateProfilePriorityService(repository)
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from types import SimpleNamespace\n"
        "from services.candidate_profile_priority_service import CandidateProfilePriorityNotFoundError\n"
        "candidate_id = 'a'\n"
        "profile_runtime = SimpleNamespace(priorities=st.session_state.priorities)\n"
        + ast.unparse(section)
    )
    app.session_state.priorities = service
    app.run()
    assert not app.exception
    if not candidate_exists:
        assert not app.button
        repository.save.assert_not_called()
        return
    assert any(item.value == "No current priorities added yet." for item in app.info)
    app.button[0].click().run()
    assert any(item.value == "Write a priority before adding it." for item in app.warning)
    repository.save.assert_not_called()
    app.text_input(key="new_priority_text").set_value("  More flexibility  ")
    app.selectbox(key="new_priority_direction").select("negative")
    app.button[0].click().run()
    assert not app.exception
    assert service.list("a")[0].text == "More flexibility"
    assert service.list("a")[0].direction == "negative"
    assert service.list("a")[0].active is True
    app.text_input(key="priority_text_a_0").set_value("New direction")
    app.selectbox(key="priority_direction_a_0").select("positive")
    app.checkbox(key="priority_active_a_0").uncheck()
    app.button(key="save_priority_a_0").click().run()
    assert not app.exception
    assert service.list("a")[0].text == "New direction"
    assert service.list("a")[0].direction == "positive"
    assert service.list("a")[0].active is False
    app.button(key="remove_priority_a_0").click().run()
    assert not app.exception
    assert service.list("a") == ()
    assert repository.save.call_count == 3
    assert repository.get.return_value.professional_summary == "Unchanged"


def test_experience_tab_retains_explicit_source_record_boundary():
    tree = ast.parse(Path("pages/3_Profile.py").read_text(encoding="utf-8"))
    tab = next(node for node in ast.walk(tree) if isinstance(node, ast.With)
               and any(isinstance(item.context_expr, ast.Name)
                       and item.context_expr.id == "experience_tab" for item in node.items))
    source = ast.unparse(tab)
    assert "onboarding_repository.list_work_experiences(candidate_id)" in source
    assert "onboarding_repository.update_work_experience(" in source
    assert "confirmed_source_edit=source_edit_confirmed" in source
    assert "onboarding_repository.delete_work_experience(" in source
    assert "experience.confirmed_interview_answers" in source
    assert "experience.career_story" in source
    assert "experience.day_to_day_narrative" in source
    assert "current_profile" not in source
    assert "generated_candidate" not in source


@pytest.mark.parametrize("has_snapshot,has_legacy", [(True, True), (True, False),
                                                       (False, True), (False, False)])
def test_profile_details_present_canonical_data_without_legacy_fallback(has_snapshot, has_legacy):
    tree = ast.parse(Path("pages/3_Profile.py").read_text(encoding="utf-8"))
    # Run the actual presentation statements without bootstrapping the authenticated page.
    details = [node for node in ast.walk(tree) if isinstance(node, ast.If) and (
        ast.unparse(node.test) in {
            "current_profile is not None",
            "current_profile is not None and current_profile.languages",
        })]
    assert len(details) == 2
    presentation = "\n".join(ast.unparse(node) for node in sorted(details, key=lambda node: node.lineno))
    profile = SimpleNamespace(
        profile_version=1, objectives=(), evidence_gaps=("Canonical evidence gap",),
        capabilities=(SimpleNamespace(label="Canonical proven", transferable=False),
                      SimpleNamespace(label="Canonical transferable", transferable=True)),
        languages=(SimpleNamespace(name="Canonical language"),),
        checkpoint=SimpleNamespace(current_position="Current role",
                                   proven_strengths=("Canonical strength",), transferable_strengths=()),
    )
    legacy = SimpleNamespace(
        proven_capabilities=["Legacy proven"], transferable_capabilities=["Legacy transferable"],
        strengths=["Legacy strength"], development_areas=["Legacy gap"],
        spoken_languages=["Legacy language"], developing_capabilities=["Legacy developing"],
        technical_tools=["Legacy tool"], domain_experience=["Legacy domain"],
        professional_experiences=[SimpleNamespace(stated_role="Legacy role", inferred_role=None,
            company="Legacy company", role_family=None, summary="Legacy experience",
            demonstrated_capabilities=[], evidence=[])],
    )
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from components.workpilot_ui import render_profile_snapshot\n"
        "current_profile = st.session_state.profile\n"
        "generated_candidate = st.session_state.legacy\n"
        "render_profile_snapshot(current_profile)\n" + presentation
    )
    app.session_state.profile = profile if has_snapshot else None
    app.session_state.legacy = legacy if has_legacy else None
    app.run()
    assert not app.exception
    text = "\n".join(item.value for item in app.markdown)
    for value in ("Canonical proven", "Canonical transferable", "Canonical strength",
                  "Canonical language", "Canonical evidence gap"):
        assert (value in text) == has_snapshot
    for value in ("Legacy proven", "Legacy transferable", "Legacy strength", "Legacy gap", "Legacy language"):
        assert value not in text
    for value in ("Legacy developing", "Legacy tool", "Legacy domain", "Legacy experience"):
        assert value not in text
    for label in ("Tools & domain experience", "Currently developing", "Professional evidence"):
        assert label not in text
        assert label not in [item.label for item in app.expander]
    if has_snapshot:
        proven = "\n".join(item.value for item in app.columns[0].markdown)
        transferable = "\n".join(item.value for item in app.columns[1].markdown)
        assert "Canonical proven" in proven and "Canonical transferable" not in proven
        assert "Canonical transferable" in transferable and "Canonical proven" not in transferable
