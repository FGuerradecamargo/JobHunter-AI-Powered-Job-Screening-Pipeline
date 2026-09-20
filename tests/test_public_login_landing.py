"""Exercise the real login page with offline authentication doubles."""
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


PAGE = Path(__file__).resolve().parents[1] / "pages" / "0_Login.py"


@pytest.fixture
def login_page(monkeypatch):
    user = SimpleNamespace(id=7, candidate_id=8, display_name="Test", access_level="user")
    oidc = SimpleNamespace(is_logged_in=False, get=lambda key, default=None: default)
    auth = Mock()
    auth.authenticate.return_value = user
    auth.register.return_value = user
    google = Mock()
    google.register.return_value = user
    google.link_existing_account.return_value = user
    identity = Mock()
    identity.resolve.return_value = SimpleNamespace(status="linked", user=user)
    recovery = Mock(return_value="Check your inbox if your account supports password sign-in.")
    verification = Mock()
    events = []

    class FakeAuthService:
        def __new__(cls):
            return auth

    def login(value):
        events.append("login")
        st.session_state["test_user"] = value

    def logout():
        events.append("logout")
        st.session_state.pop("test_user", None)

    def module(name, **attributes):
        result = ModuleType(name)
        result.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, result)

    module("services.session_auth", get_authenticated_user=lambda: st.session_state.get("test_user"),
           login_user=login, logout_user=logout)
    module("services.auth_service", AuthService=FakeAuthService)
    module("services.account_recovery_service", AccountRecoveryService=SimpleNamespace(request_password_reset=recovery))
    module("services.email_verification_delivery_service", EmailVerificationDeliveryService=SimpleNamespace(send_verification_email=verification))
    module("services.google_account_service", GoogleAccountService=lambda: google)
    factory = Mock(return_value=identity)
    factory.LINKED = "linked"
    factory.REGISTRATION_REQUIRED = "registration_required"
    factory.LINK_REQUIRED = "link_required"
    module("services.google_identity_service", GoogleIdentityService=factory)
    monkeypatch.setattr(st, "user", oidc)
    monkeypatch.setattr(st, "login", lambda provider: events.append(provider))
    monkeypatch.setattr(st, "logout", lambda: events.append("oidc_logout"))
    monkeypatch.setattr(st, "switch_page", lambda page: events.append(page))
    return SimpleNamespace(app=AppTest.from_file(str(PAGE)), user=user, oidc=oidc,
                           auth=auth, google=google, identity=identity, recovery=recovery,
                           verification=verification, events=events)


def html(app):
    return "\n".join(element.proto.body for element in app.get("html"))


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_dedicated_login_keeps_auth_controls_without_marketing(login_page):
    app = login_page.app.run()
    assert not app.exception
    markup = html(app)
    assert "Finding a job" not in markup
    assert "Welcome to" in markup
    assert "wp-auth-intro" in markup
    assert "<script" not in markup
    assert [tab.label for tab in app.tabs] == ["Log in", "Create account"]
    assert {"Continue with Google", "Log in", "Create account", "Send reset instructions"} <= {b.label for b in app.button}
    assert not login_page.auth.authenticate.called
    assert not login_page.auth.register.called
    assert not login_page.recovery.called
    assert not login_page.verification.called


def test_authenticated_branch_hides_landing_preserves_navigation_and_logout(login_page):
    app = login_page.app
    app.session_state["test_user"] = login_page.user
    app.run()
    assert not app.exception
    assert "wp-public-home" not in html(app)
    assert not app.tabs
    button(app, "Go to profile").click().run()
    assert "pages/3_Profile.py" in login_page.events
    button(app, "Log out").click().run()
    assert "logout" in login_page.events
    assert "Welcome to" in html(app)


def test_email_login_preserved(login_page):
    app = login_page.app.run()
    app.text_input[0].input("test@example.invalid")
    app.text_input[1].input("test-password")
    button(app, "Log in").click().run()
    login_page.auth.authenticate.assert_called_once_with(email="test@example.invalid", password="test-password")
    assert login_page.events == ["login"]
    assert "Finding a job" not in html(app)


def test_invalid_login_still_rejected(login_page):
    login_page.auth.authenticate.return_value = None
    app = login_page.app.run()
    button(app, "Log in").click().run()
    assert app.error[0].value == "Invalid email or password."
    assert not login_page.events


def test_signup_and_verification_preserved(login_page):
    app = login_page.app.run()
    app.text_input(key="signup_email").input("test@example.invalid")
    app.text_input(key="signup_password").input("test-password")
    next(item for item in app.text_input if item.label == "Confirm password").input("test-password")
    button(app, "Create account").click().run()
    assert login_page.auth.register.call_count == 1
    login_page.verification.assert_called_once_with(7)
    assert login_page.events == ["login"]


def test_password_recovery_preserved(login_page):
    app = login_page.app.run()
    app.text_input(key="password_recovery_email").input("test@example.invalid")
    button(app, "Send reset instructions").click().run()
    login_page.recovery.assert_called_once_with("test@example.invalid")


def test_google_sign_in_control_preserved(login_page):
    app = login_page.app.run()
    button(app, "Continue with Google").click().run()
    assert login_page.events == ["google"]


@pytest.mark.parametrize("status", ["linked", "registration_required"])
def test_google_callback_preserved_without_public_hero(login_page, status):
    login_page.oidc.is_logged_in = True
    login_page.identity.resolve.return_value.status = status
    app = login_page.app.run()
    assert not app.exception
    assert login_page.events == ["login"]
    assert "Finding a job" not in html(app)
    assert login_page.google.register.call_count == (status == "registration_required")


def test_existing_account_google_linking_preserved(login_page):
    login_page.oidc.is_logged_in = True
    login_page.identity.resolve.return_value = SimpleNamespace(status="link_required", email="test@example.invalid")
    app = login_page.app.run()
    assert "Finding a job" not in html(app)
    assert not app.tabs
    app.text_input[0].input("test-password")
    button(app, "Connect Google account").click().run()
    assert not app.exception
    login_page.google.link_existing_account.assert_called_once()
    assert login_page.events == ["login"]


def test_expired_google_session_guard_preserved(login_page):
    login_page.oidc.is_logged_in = True
    app = login_page.app
    app.session_state["reauthentication_required"] = True
    app.run()
    assert not login_page.identity.resolve.called
    assert not app.tabs
    assert "Finding a job" not in html(app)
    button(app, "Restart Google sign-in").click().run()
    assert login_page.events == ["oidc_logout"]


@pytest.fixture
def root_page(login_page, monkeypatch):
    import services.database as database
    import services.candidate_repository as candidates
    import services.user_context_runtime as context

    bootstrap = Mock(side_effect=AssertionError("Public home must not bootstrap the database"))
    dashboard_context = Mock(return_value=SimpleNamespace(active_user=login_page.user))
    candidate_repository = Mock()
    candidate_repository.get.return_value = None
    require_user = Mock(return_value=login_page.user)
    session = sys.modules["services.session_auth"]
    monkeypatch.setattr(session, "require_authenticated_user", require_user, raising=False)
    monkeypatch.setattr(session, "render_logout_button", Mock(), raising=False)
    monkeypatch.setattr(database, "initialize_database", bootstrap)
    monkeypatch.setattr(candidates, "CandidateRepository", lambda: candidate_repository)
    monkeypatch.setattr(context, "get_active_user_context", dashboard_context)
    return SimpleNamespace(app=AppTest.from_file(str(PAGE.parents[1] / "app.py")),
                           bootstrap=bootstrap, context=dashboard_context, require_user=require_user,
                           repository=candidate_repository, login=login_page)


def test_public_root_stops_before_dashboard_or_bootstrap(root_page):
    app = root_page.app.run()
    assert not app.exception
    markup = html(app)
    assert "Finding a job" in markup
    assert "Illustrative numbers, not live market statistics" in markup
    assert "Illustrative opportunity. Not a live vacancy" in markup
    assert "Career Dashboard" not in markup
    assert not app.text_input
    root_page.bootstrap.assert_not_called()
    root_page.require_user.assert_not_called()
    root_page.context.assert_not_called()
    root_page.repository.get.assert_not_called()


def test_authenticated_root_continues_original_dashboard(root_page):
    root_page.bootstrap.side_effect = None
    app = root_page.app
    app.session_state["test_user"] = root_page.login.user
    app.run()
    assert not app.exception
    assert "Career Dashboard" in html(app)
    assert "Finding a job" not in html(app)
    assert "wp-seasonal" not in html(app)
    root_page.bootstrap.assert_called_once()
    root_page.require_user.assert_called_once()
    root_page.context.assert_called_once_with(authenticated_user=root_page.login.user)
    root_page.repository.get.assert_called_once_with(8)


@pytest.mark.parametrize("key,intent", [
    ("public_start_career", "signup"),
    ("public_closing_start", "signup"),
    ("public_existing_account", "login"),
])
def test_public_ctas_use_supported_login_navigation(root_page, key, intent):
    app = root_page.app.run()
    app.button(key=key).click().run()
    assert not app.exception
    assert root_page.login.events == ["pages/0_Login.py"]
    assert app.session_state["public_auth_intent"] == intent


def test_signup_intent_is_presentation_only(login_page):
    app = login_page.app
    app.session_state["public_auth_intent"] = "signup"
    app.run()
    assert not app.exception
    assert app.header[0].value == "Start with your career."
    assert [tab.label for tab in app.tabs] == ["Log in", "Create account"]
    assert not login_page.events
    assert not login_page.auth.register.called
    button(app, "Back to Home").click().run()
    assert login_page.events == ["app.py"]


def test_production_shell_routes_public_default_to_app(root_page):
    app = AppTest.from_file(str(PAGE.parents[1] / "streamlit_app.py")).run()
    assert not app.exception
    assert "Finding a job" in html(app)
    root_page.bootstrap.assert_not_called()
    root_page.context.assert_not_called()


def test_production_shell_preserves_pending_google_routing(root_page):
    root_page.login.oidc.is_logged_in = True
    app = AppTest.from_file(str(PAGE.parents[1] / "streamlit_app.py")).run()
    assert not app.exception
    assert len(root_page.login.events) == 1
    assert root_page.login.events[0].url_path == "Login"
    root_page.bootstrap.assert_not_called()
