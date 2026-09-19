"""Exercise the real page callback without loading clients or the live app."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from models.gmail_connection import GmailConnection
from services.provider_failure import log_failure


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def callback():
    source = (ROOT / "pages/2_Sources.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"get_query_parameter", "handle_oauth_callback"}]
    ui = SimpleNamespace(query_params={"code": "code", "state": "state"},
                         error=Mock(), success=Mock(), switch_page=Mock(), rerun=Mock())
    state = SimpleNamespace(user_id="owner", code_verifier="verifier")
    result = SimpleNamespace(gmail_address="owner@example.test", access_token="fake",
                             refresh_token="fake", token_expiry=None, scopes=[])
    env = dict(st=ui, authenticated_user=SimpleNamespace(id="actor"),
               active_user=SimpleNamespace(id="owner"), GmailConnection=GmailConnection,
               oauth_state_repository=Mock(), oauth_service=Mock(),
               gmail_repository=Mock(), gmail_access_audit=Mock(), logger=Mock(), log_failure=log_failure)
    env["oauth_state_repository"].consume.return_value = state
    env["oauth_service"].exchange_authorization_code.return_value = result
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(ROOT / "pages/2_Sources.py"), "exec"), env)
    return env


def test_success_persists_then_clears_and_switches_to_sources(callback):
    ui = callback["st"]
    ui.query_params["next"] = "https://untrusted.example/"
    def navigated(path):
        assert path == "pages/2_Sources.py"
        assert ui.query_params == {}
        callback["gmail_repository"].save.assert_called_once()
    ui.switch_page.side_effect = navigated
    callback["handle_oauth_callback"]()
    callback["oauth_state_repository"].consume.assert_called_once_with(
        "state", initiated_by_user_id="actor")
    callback["oauth_service"].exchange_authorization_code.assert_called_once_with(
        authorization_code="code", expected_state="state", code_verifier="verifier")
    assert callback["gmail_repository"].save.call_args.args[0].user_id == "owner"
    ui.switch_page.assert_called_once_with("pages/2_Sources.py")
    ui.rerun.assert_not_called()


def test_invalid_or_expired_state_fails_closed(callback):
    callback["oauth_state_repository"].consume.return_value = None
    callback["handle_oauth_callback"]()
    assert callback["st"].query_params == {}
    callback["st"].error.assert_called_once()
    callback["st"].switch_page.assert_not_called()
    callback["oauth_service"].exchange_authorization_code.assert_not_called()
    callback["gmail_repository"].save.assert_not_called()


def test_provider_error_does_not_redirect_as_success(callback):
    callback["st"].query_params["error"] = "access_denied"
    callback["handle_oauth_callback"]()
    assert callback["st"].query_params == {}
    callback["st"].switch_page.assert_not_called()
    callback["st"].success.assert_not_called()
    callback["oauth_state_repository"].consume.assert_not_called()


@pytest.mark.parametrize("failing", ["oauth_service", "gmail_repository"])
def test_exchange_or_save_error_never_navigates(callback, failing):
    method = "save" if failing == "gmail_repository" else "exchange_authorization_code"
    getattr(callback[failing], method).side_effect = RuntimeError("fake failure")
    callback["handle_oauth_callback"]()
    callback["st"].switch_page.assert_not_called()
    callback["st"].success.assert_not_called()


def test_sources_route_is_explicit():
    tree = ast.parse((ROOT / "streamlit_app.py").read_text(encoding="utf-8"))
    pages = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "Page"
             and node.args and isinstance(node.args[0], ast.Constant)
             and node.args[0].value == "pages/2_Sources.py"]
    assert len(pages) == 1
    assert any(k.arg == "url_path" and k.value.value == "Sources" for k in pages[0].keywords)
