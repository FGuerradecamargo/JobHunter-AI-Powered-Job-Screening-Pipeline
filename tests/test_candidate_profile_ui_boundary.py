import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from services import candidate_profile_runtime as runtime


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
    snapshots, generation, readiness, service, gateway = (Mock() for _ in range(5))
    factories = []
    for name, value in (("ProfileSnapshotRepository", snapshots),
                        ("CandidateProfileGenerationService", generation),
                        ("ProfileReadinessService", readiness),
                        ("CandidateProfileService", service), ("CandidateProfileGateway", gateway)):
        factory = Mock(return_value=value)
        monkeypatch.setattr(runtime, name, factory)
        factories.append(factory)
    onboarding, updates, candidate = Mock(), Mock(), Mock()
    result = runtime.create_candidate_profile_runtime(onboarding_repository=onboarding,
        career_update_repository=updates, candidate_repository=candidate)
    assert result.service is service
    assert result.onboarding_gateway is gateway
    kwargs = factories[1].call_args.kwargs
    assert kwargs["onboarding_repository"] is onboarding
    assert kwargs["career_update_repository"] is updates
    assert kwargs["candidate_repository"] is candidate
    assert kwargs["snapshot_repository"] is snapshots
    factories[2].assert_called_once_with(snapshots=snapshots, onboarding=onboarding, updates=updates)
    factories[3].assert_called_once_with(snapshot_repository=snapshots,
        readiness_service=readiness, generation_service=generation)
    factories[4].assert_called_once_with(generation)
    assert not generation.mock_calls


def test_profile_presentation_has_no_duplicate_canonical_candidate_reads():
    tree = ast.parse(Path("pages/3_Profile.py").read_text(encoding="utf-8"))
    reads = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
             and isinstance(node.value, ast.Name) and node.value.id == "generated_candidate"}
    assert not reads & {"proven_capabilities", "transferable_capabilities", "strengths",
                        "development_areas", "spoken_languages"}
    assert {"developing_capabilities", "technical_tools", "domain_experience",
            "professional_experiences"} <= reads
    source = ast.unparse(tree)
    assert "candidate_repository.get(" in source
    assert "priority_candidate = generated_candidate" in source
    assert "priority_candidate.priorities.append(" in source
    assert "priority_candidate.priorities.pop(" in source
    assert "candidate_repository.save(priority_candidate)" in source


@pytest.mark.parametrize("has_snapshot,has_legacy", [(True, True), (True, False),
                                                       (False, True), (False, False)])
def test_profile_details_present_canonical_data_without_legacy_fallback(has_snapshot, has_legacy):
    tree = ast.parse(Path("pages/3_Profile.py").read_text(encoding="utf-8"))
    # Run the actual presentation statements without bootstrapping the authenticated page.
    details = [node for node in ast.walk(tree) if isinstance(node, ast.If) and (
        ast.unparse(node.test) in {
            "current_profile is not None or generated_candidate is not None",
            "current_profile is not None and current_profile.languages",
        } or (ast.unparse(node.test) == "generated_candidate is not None"
              and "Tools & domain experience" in ast.unparse(node)))]
    assert len(details) == 3
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
        assert (value in text) == has_legacy
    if has_snapshot:
        proven = "\n".join(item.value for item in app.columns[0].markdown)
        transferable = "\n".join(item.value for item in app.columns[1].markdown)
        assert "Canonical proven" in proven and "Canonical transferable" not in proven
        assert "Canonical transferable" in transferable and "Canonical proven" not in transferable
