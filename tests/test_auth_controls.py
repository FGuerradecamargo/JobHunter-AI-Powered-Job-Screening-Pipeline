import os
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("SESSION_COOKIE_KEY", "test-only-session-cookie-key")

from components import auth_controls
from services import authentication_runtime
from services import streamlit_oidc


@pytest.fixture
def controls(monkeypatch):
    user = SimpleNamespace(display_name="Synthetic")
    resolve = Mock(return_value=user)
    logout = Mock()
    external = Mock(return_value=False)
    ui = SimpleNamespace(sidebar=nullcontext(), caption=Mock(),
                         button=Mock(return_value=False), rerun=Mock())
    monkeypatch.setattr(auth_controls, "get_authenticated_user", resolve)
    monkeypatch.setattr(auth_controls, "logout_user", logout)
    monkeypatch.setattr(auth_controls, "logout_external_identity_if_active", external)
    monkeypatch.setattr(auth_controls, "st", ui)
    return SimpleNamespace(user=user, resolve=resolve, logout=logout, external=external, ui=ui)


@pytest.mark.parametrize("reuse", [False, True])
def test_logout_render_reuses_only_explicit_current_render_user(controls, reuse):
    auth_controls.render_logout_button(**({"authenticated_user": controls.user} if reuse else {}))
    assert controls.resolve.call_count == (0 if reuse else 1)
    controls.ui.caption.assert_called_once_with("Signed in as Synthetic")
    controls.ui.button.assert_called_once_with(
        "Log out", use_container_width=True, key="global_logout_button")
    controls.logout.assert_not_called()
    controls.external.assert_not_called()
    controls.ui.rerun.assert_not_called()


def test_no_user_renders_nothing(controls):
    controls.resolve.return_value = None
    auth_controls.render_logout_button()
    controls.ui.caption.assert_not_called()
    controls.ui.button.assert_not_called()
    controls.logout.assert_not_called()
    controls.external.assert_not_called()


@pytest.mark.parametrize("active", [False, True])
def test_logout_orders_workpilot_external_and_rerun(controls, active):
    events = []
    controls.ui.button.return_value = True
    controls.logout.side_effect = lambda: events.append("workpilot")
    controls.external.side_effect = lambda: events.append("external") or active
    controls.ui.rerun.side_effect = lambda: events.append("rerun")
    auth_controls.render_logout_button(authenticated_user=controls.user)
    assert events == ["workpilot", "external", "rerun"]
    controls.logout.assert_called_once_with()
    controls.external.assert_called_once_with()


def test_external_redirect_preserves_workpilot_logout(controls):
    class Redirect(BaseException):
        pass
    controls.ui.button.return_value = True
    controls.external.side_effect = Redirect
    with pytest.raises(Redirect):
        auth_controls.render_logout_button(authenticated_user=controls.user)
    controls.logout.assert_called_once_with()
    controls.ui.rerun.assert_not_called()


@pytest.mark.parametrize("active", [False, True])
def test_runtime_logs_out_external_identity_only_when_active(monkeypatch, active):
    logout = Mock()
    monkeypatch.setattr(streamlit_oidc.st, "user", SimpleNamespace(is_logged_in=active))
    monkeypatch.setattr(streamlit_oidc.st, "logout", logout)
    assert authentication_runtime.authentication_continuation_required() is active
    assert authentication_runtime.logout_external_identity_if_active() is active
    assert logout.call_count == int(active)


def test_session_shell_and_controls_are_provider_free():
    for filename in ("services/session_auth.py", "streamlit_app.py", "components/auth_controls.py"):
        source = Path(filename).read_text(encoding="utf-8").lower()
        for forbidden in ("oidc", "google", "st.user", "st.logout"):
            assert forbidden not in source
    session = Path("services/session_auth.py").read_text(encoding="utf-8")
    assert "render_logout_button" not in session
    assert "authentication_continuation_required" not in session
    shell = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "from services.authentication_runtime import authentication_continuation_required" in shell
    for filename in ("app.py", "pages/1_Opportunities.py", "pages/2_Sources.py",
                     "pages/3_Profile.py", "pages/4_Improvements.py", "pages/6_Settings.py"):
        assert "from components.auth_controls import render_logout_button" in Path(filename).read_text(encoding="utf-8")
