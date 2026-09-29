import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_public_cookie_recovery_is_nonblocking_before_navigation():
    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    public_recovery = source.index(
        "get_authenticated_user_if_ready()"
    )

    public_navigation = source.index(
        "st.navigation("
    )

    assert public_recovery < public_navigation

    # A cached UI identity never bypasses durable validation.
    assert (
        "else:\n"
        "    # Never authorize the private shell "
        "from session_state alone.\n"
        "    authenticated_user = "
        "get_authenticated_user()"
        in source
    )


def test_missing_snapshot_stops_before_search_and_clears_pending_run():
    source = Path("pages/1_Opportunities.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    gate = next(n for n in tree.body if isinstance(n, ast.If)
                and ast.unparse(n.test) == "not readiness.ready")
    creation = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == "OpportunitySearchRun")
    assert gate.lineno < creation.lineno
    class Stopped(BaseException):
        pass
    st = Mock()
    st.session_state = {"scan_requested": True, "opportunity_search_run": object()}
    st.stop.side_effect = Stopped
    with pytest.raises(Stopped):
        exec(compile(ast.Module(body=[gate], type_ignores=[]), "gate", "exec"),
             {"st": st, "readiness": SimpleNamespace(ready=False, message="Open Profile")})
    assert not st.session_state["scan_in_progress"]
    assert "opportunity_search_run" not in st.session_state
    st.page_link.assert_called_once_with("pages/3_Profile.py", label="Open Profile")


@pytest.mark.parametrize("ready,actor", [(False, "actor"), (True, "other")])
def test_fragment_revalidates_scope_and_readiness_before_work(ready, actor):
    from services.opportunity_search_run import OpportunitySearchRun
    source = Path("pages/1_Opportunities.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                and n.name == "render_search_progress")
    node.decorator_list = []
    run = OpportunitySearchRun("actor", "owner", "candidate", "signature", 10, {})
    class Rerun(BaseException):
        pass
    st = Mock()
    st.session_state = {"opportunity_search_run": run, "scan_in_progress": True}
    st.rerun.side_effect = Rerun
    unit = Mock()
    current = SimpleNamespace(ready=ready, snapshot=SimpleNamespace(memory_signature="same"))
    env = dict(st=st, search_scope=run.scope, candidate_id="candidate", readiness=current,
               profile_readiness=lambda _: current, advance_opportunity_search=unit,
               require_authenticated_user=lambda: SimpleNamespace(id=actor),
               get_active_user_context=lambda **kw: SimpleNamespace(active_user=SimpleNamespace(id="owner", candidate_id="candidate")))
    exec(compile(ast.Module(body=[node], type_ignores=[]), "fragment", "exec"), env)
    with pytest.raises(Rerun):
        env["render_search_progress"]()
    assert run.status == "stopped"
    unit.assert_not_called()
