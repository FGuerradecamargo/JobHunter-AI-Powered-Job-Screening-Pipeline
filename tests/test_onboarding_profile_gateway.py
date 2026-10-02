import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, create_autospec, call

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
    assert "from services.profile_gateway import ProfileGateway" in source
    assert "def render_onboarding(" in source
    assert "render_profile_onboarding" not in source
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == "generate" for node in ast.walk(tree))
    page = Path("pages/3_Profile.py").read_text(encoding="utf-8")
    assert "from components.onboarding import render_onboarding" in page
    assert "profile_gateway=profile_runtime.onboarding_gateway" in page
    runtime = Path("services/candidate_profile_runtime.py").read_text(encoding="utf-8")
    assert "onboarding_gateway=CandidateProfileGateway(generation)" in runtime


@pytest.mark.parametrize("fails", [False, True])
def test_terminal_gateway_preserves_state_events_and_failure_behavior(fails):
    tree = ast.parse(Path("components/onboarding.py").read_text(encoding="utf-8"))
    terminal = next(node for node in ast.walk(tree) if isinstance(node, ast.Try)
                    and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                            and child.func.attr == "create_initial_profile" for child in ast.walk(node)))
    class Rerun(BaseException):
        pass
    st = Mock()
    st.spinner.return_value = nullcontext()
    st.session_state = {"step": 4}
    st.rerun.side_effect = Rerun
    gateway = Mock()
    if fails:
        gateway.create_initial_profile.side_effect = RuntimeError("private failure")
    events = Mock()
    env = dict(st=st, profile_gateway=gateway, candidate_id="c", candidate_name="Synthetic",
               step_key="step", inputs=SimpleNamespace(event=events), logger=Mock())
    code = compile(ast.Module(body=[terminal], type_ignores=[]), "terminal", "exec")
    if fails:
        exec(code, env)
        assert st.session_state == {"step": 4}
        events.assert_not_called()
        st.success.assert_not_called()
        st.rerun.assert_not_called()
        st.error.assert_called_once_with("We could not build your Career Profile. Please try again.")
    else:
        with pytest.raises(Rerun):
            exec(code, env)
        assert "step" not in st.session_state
        assert events.call_args_list == [call("onboarding_step_completed"),
            call("onboarding_completed", once=True), call("candidate_profile_created", once=True)]
        st.success.assert_called_once_with("Your Career Profile is ready.")
        st.error.assert_not_called()
    gateway.create_initial_profile.assert_called_once_with(candidate_id="c", candidate_name="Synthetic")
