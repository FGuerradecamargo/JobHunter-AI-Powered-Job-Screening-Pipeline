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



def test_protected_route_guard_waits_for_cookie_recovery():
    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    guard = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_require_sign_in"
    )

    class Rerun(BaseException):
        pass

    st = Mock()
    st.rerun.side_effect = Rerun

    authenticated_user = object()
    get_authenticated_user = Mock(
        return_value=authenticated_user
    )

    login_page = object()

    environment = {
        "st": st,
        "get_authenticated_user": (
            get_authenticated_user
        ),
        "login_page": login_page,
    }

    exec(
        compile(
            ast.Module(
                body=[guard],
                type_ignores=[],
            ),
            "streamlit_app.py",
            "exec",
        ),
        environment,
    )

    with pytest.raises(Rerun):
        environment[
            "_require_sign_in"
        ]()

    get_authenticated_user.assert_called_once_with()
    st.switch_page.assert_not_called()


def test_protected_route_guard_redirects_after_cookie_resolution():
    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    guard = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_require_sign_in"
    )

    st = Mock()
    get_authenticated_user = Mock(
        return_value=None
    )
    login_page = object()

    environment = {
        "st": st,
        "get_authenticated_user": (
            get_authenticated_user
        ),
        "login_page": login_page,
    }

    exec(
        compile(
            ast.Module(
                body=[guard],
                type_ignores=[],
            ),
            "streamlit_app.py",
            "exec",
        ),
        environment,
    )

    environment[
        "_require_sign_in"
    ]()

    get_authenticated_user.assert_called_once_with()

    st.switch_page.assert_called_once_with(
        login_page
    )


def test_login_route_remains_registered_when_authenticated():
    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    login_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "login_page"
            for target in node.targets
        )
    )

    assert isinstance(
        login_assignment.value,
        ast.Call,
    )

    visibility = next(
        keyword.value
        for keyword
        in login_assignment.value.keywords
        if keyword.arg == "visibility"
    )

    assert ast.literal_eval(
        visibility
    ) == "hidden"

    authenticated_navigation_lists = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "navigation"
            and node.args
            and isinstance(node.args[0], ast.List)
        ):
            names = {
                element.id
                for element in node.args[0].elts
                if isinstance(element, ast.Name)
            }

            if (
                "password_reset_page" in names
                and "email_verification_page" in names
            ):
                authenticated_navigation_lists.append(
                    names
                )

    assert any(
        "login_page" in names
        for names
        in authenticated_navigation_lists
    )

    private_extensions = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "extend"
            and isinstance(
                node.func.value,
                ast.Name,
            )
            and node.func.value.id
            == "private_pages"
            and node.args
            and isinstance(
                node.args[0],
                ast.List,
            )
        ):
            continue

        private_extensions.append(
            {
                element.id
                for element
                in node.args[0].elts
                if isinstance(
                    element,
                    ast.Name,
                )
            }
        )

    assert any(
        {
            "password_reset_page",
            "email_verification_page",
            "login_page",
        }.issubset(names)
        for names in private_extensions
    )
