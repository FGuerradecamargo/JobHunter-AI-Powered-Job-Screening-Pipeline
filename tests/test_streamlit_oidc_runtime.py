from types import SimpleNamespace
import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

import services.streamlit_oidc as oidc


def test_oidc_absent_fails_closed(monkeypatch):
    monkeypatch.setattr(
        oidc.st,
        "user",
        SimpleNamespace(),
    )

    assert oidc.oidc_available() is False
    assert oidc.oidc_logged_in() is False


def test_oidc_configured_logged_out(monkeypatch):
    monkeypatch.setattr(
        oidc.st,
        "user",
        SimpleNamespace(
            is_logged_in=False,
        ),
    )

    assert oidc.oidc_available() is True
    assert oidc.oidc_logged_in() is False


def test_oidc_configured_logged_in(monkeypatch):
    monkeypatch.setattr(
        oidc.st,
        "user",
        SimpleNamespace(
            is_logged_in=True,
        ),
    )

    assert oidc.oidc_available() is True
    assert oidc.oidc_logged_in() is True


def test_runtime_has_no_unsafe_direct_oidc_access():
    from pathlib import Path

    for filename in (
        "streamlit_app.py",
        "pages/0_Login.py",
        "services/session_auth.py",
    ):
        source = Path(filename).read_text(
            encoding="utf-8"
        )

        assert "st.user.is_logged_in" not in source


def test_public_cookie_bootstrap_does_not_block_navigation_and_preserves_auth_route():
    from pathlib import Path

    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    public_gate = source.index(
        'if st.session_state.get("current_user") is None:'
    )

    nonblocking_auth = source.index(
        "get_authenticated_user_if_ready()",
        public_gate,
    )

    navigation = source.index(
        "st.navigation(",
        nonblocking_auth,
    )

    assert (
        public_gate
        < nonblocking_auth
        < navigation
    )

    assert "authentication_continuation_required()" in source
    assert "st.switch_page(" in source

    # Private navigation still requires durable session validation.
    private_validation = source.index(
        "authenticated_user = get_authenticated_user()",
        nonblocking_auth,
    )

    assert private_validation < navigation


def test_shell_has_no_provider_auth_dependency():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    for forbidden in ("oidc_logged_in", "services.streamlit_oidc", "st.user", "google"):
        assert forbidden not in source.lower()
    login = Path("pages/0_Login.py").read_text(encoding="utf-8")
    assert "oidc_logged_in()" in login


@pytest.mark.parametrize("pending", [False, True])
def test_session_boundary_reports_continuation_without_session_authorization(pending):
    tree = ast.parse(Path("services/authentication_runtime.py").read_text(encoding="utf-8"))
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "authentication_continuation_required")
    provider = Mock(return_value=pending)
    env = {"oidc_logged_in": provider}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), "boundary", "exec"), env)
    assert env[helper.name]() is pending
    provider.assert_called_once_with()


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("pending", [False, True])
def test_shell_routes_unfinished_auth_only_through_boundary(cached, pending):
    tree = ast.parse(Path("streamlit_app.py").read_text(encoding="utf-8"))
    gate_index = next(i for i, node in enumerate(tree.body) if isinstance(node, ast.If)
                      and ast.unparse(node.test) == "st.session_state.get('current_user') is None")
    gate, pending_assignment, navigation_gate = tree.body[gate_index:gate_index + 3]
    st = Mock()
    st.session_state = {"current_user": object()} if cached else {}
    st.navigation.return_value = SimpleNamespace(url_path="")
    resolve = Mock(return_value=None)
    nonblocking = Mock(return_value=None)
    continuation = Mock(return_value=pending)
    login_page = SimpleNamespace(url_path="Login")
    env = dict(st=st, get_authenticated_user=resolve,
               get_authenticated_user_if_ready=nonblocking,
               authentication_continuation_required=continuation,
               public_pages=[], login_page=login_page)
    exec(compile(ast.Module(body=[gate, pending_assignment, navigation_gate], type_ignores=[]),
                 "shell", "exec"), env)
    (resolve if cached else nonblocking).assert_called_once_with()
    (nonblocking if cached else resolve).assert_not_called()
    assert env["authenticated_user"] is None
    assert st.session_state["workpilot_public_navigation"] is True
    if pending:
        st.switch_page.assert_called_once_with(login_page)
    else:
        st.switch_page.assert_not_called()


def test_private_shell_revalidates_cached_identity():
    from pathlib import Path

    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "# Never authorize the private shell "
        "from session_state alone."
        in source
    )

    assert (
        "authenticated_user = "
        "get_authenticated_user()"
        in source
    )
