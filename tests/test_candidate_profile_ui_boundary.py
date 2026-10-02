import ast
from pathlib import Path
from unittest.mock import Mock

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
