import ast
from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from services.candidate_profile_generation_service import CandidateProfileGenerationService
from services.profile_gateway import CandidateProfileGateway


def test_gateway_delegates_generation_without_changing_result():
    service = create_autospec(CandidateProfileGenerationService, instance=True)
    result = object()
    service.generate.return_value = result
    assert CandidateProfileGateway(service).create_initial_profile(
        candidate_id="c", candidate_name="Synthetic") is result
    service.generate.assert_called_once_with(candidate_id="c", candidate_name="Synthetic")


def test_gateway_preserves_generation_failure():
    service = Mock()
    error = RuntimeError("generation failed")
    service.generate.side_effect = error
    with pytest.raises(RuntimeError) as raised:
        CandidateProfileGateway(service).create_initial_profile(candidate_id="c", candidate_name="Synthetic")
    assert raised.value is error


def test_canonical_onboarding_boundary():
    assert not Path("components/profile_onboarding.py").exists()
    source = Path("components/onboarding.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [ast.unparse(node) for node in ast.walk(tree)
               if isinstance(node, (ast.Import, ast.ImportFrom))]
    for forbidden in ("CandidateProfileGenerationService", "ProfileInterpretationService",
                      "ProfileSnapshotRepository", "ProfileReadinessService", "CandidateRepository",
                      "CareerUpdateRepository", "job_profile", "career_memory"):
        assert not any(forbidden.lower() in item.lower() for item in imports)
    assert "profile_gateway" in source  # Retained caller compatibility, not generation authority.
    assert "def render_onboarding(" in source
    assert "render_profile_onboarding" not in source
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in ("generate", "create_initial_profile") for node in ast.walk(tree))
    page = Path("pages/3_Profile.py").read_text(encoding="utf-8")
    assert "from components.onboarding import render_onboarding" in page
    assert "profile_gateway=profile_runtime.onboarding_gateway" in page
    runtime = Path("services/candidate_profile_runtime.py").read_text(encoding="utf-8")
    assert "onboarding_gateway=CandidateProfileGateway(generation)" in runtime


def test_raw_ready_boundary_has_no_profile_generation_or_completion_events():
    tree = ast.parse(Path("components/onboarding.py").read_text(encoding="utf-8"))
    literals = {node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "onboarding_completed" not in literals
    assert "candidate_profile_created" not in literals
    assert "Your information is saved and ready for profile construction." in literals
