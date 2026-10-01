import sys
from types import SimpleNamespace
from unittest.mock import Mock, create_autospec

import pytest

from models.app_user import AppUser
from services.authentication_coordinator import (
    AuthenticationCoordinator, GoogleRegistrationError, GoogleSessionError,
)
from services.auth_service import AuthService
from services.google_account_service import GoogleAccountService
from services.google_identity_service import GoogleIdentityResolution, GoogleIdentityService


@pytest.fixture
def deps():
    auth = create_autospec(AuthService, instance=True)
    identity = create_autospec(GoogleIdentityService, instance=True)
    account = create_autospec(GoogleAccountService, instance=True)
    login = Mock()
    coordinator = AuthenticationCoordinator(
        auth_service=auth, google_identity_service=identity,
        google_account_service=account, session_login=login,
    )
    return SimpleNamespace(auth=auth, identity=identity, account=account,
                           login=login, coordinator=coordinator)


@pytest.fixture
def user():
    return AppUser("u1", "test@example.invalid", "Test", "c1", "user")


def resolution(status, user=None):
    return GoogleIdentityResolution(status, "subject", "test@example.invalid", "Test", user)


def assert_no_account_calls(deps):
    deps.account.register.assert_not_called()
    deps.account.link_existing_account.assert_not_called()


def test_valid_password(deps, user):
    deps.auth.authenticate.return_value = user
    assert deps.coordinator.authenticate_with_password(user.email, "password") is user
    deps.auth.authenticate.assert_called_once_with(user.email, "password")
    deps.login.assert_called_once_with(user)
    deps.identity.resolve.assert_not_called()
    assert_no_account_calls(deps)


def test_invalid_password(deps):
    deps.auth.authenticate.return_value = None
    assert deps.coordinator.authenticate_with_password("email", "bad") is None
    deps.login.assert_not_called()
    deps.identity.resolve.assert_not_called()
    assert_no_account_calls(deps)


def test_google_linked(deps, user):
    resolved = resolution(GoogleIdentityService.LINKED, user)
    deps.identity.resolve.return_value = resolved
    claims = {"sub": "subject"}
    result = deps.coordinator.authenticate_with_google(claims)
    assert (result.status, result.resolution, result.user) == (resolved.status, resolved, user)
    deps.identity.resolve.assert_called_once_with(claims)
    deps.login.assert_called_once_with(user)
    deps.auth.authenticate.assert_not_called()
    assert_no_account_calls(deps)


@pytest.mark.parametrize("status", [GoogleIdentityService.LINKED, "unknown"])
def test_google_invalid_resolution_fails_closed(deps, status):
    deps.identity.resolve.return_value = resolution(status)
    with pytest.raises(RuntimeError):
        deps.coordinator.authenticate_with_google({})
    deps.auth.authenticate.assert_not_called()
    deps.login.assert_not_called()
    assert_no_account_calls(deps)


def test_google_registration(deps, user):
    resolved = resolution(GoogleIdentityService.REGISTRATION_REQUIRED)
    deps.identity.resolve.return_value = resolved
    deps.account.register.return_value = user
    result = deps.coordinator.authenticate_with_google({})
    assert (result.status, result.resolution, result.user) == (resolved.status, resolved, user)
    deps.account.register.assert_called_once_with(resolved)
    deps.login.assert_called_once_with(user)
    deps.auth.authenticate.assert_not_called()
    deps.account.link_existing_account.assert_not_called()


def test_google_link_required(deps, user):
    resolved = resolution(GoogleIdentityService.LINK_REQUIRED, user)
    deps.identity.resolve.return_value = resolved
    result = deps.coordinator.authenticate_with_google({})
    assert (result.status, result.resolution, result.user) == (resolved.status, resolved, None)
    deps.auth.authenticate.assert_not_called()
    deps.login.assert_not_called()
    assert_no_account_calls(deps)


def test_link_valid_password(deps, user):
    resolved = resolution(GoogleIdentityService.LINK_REQUIRED, user)
    linked_user = AppUser("u1", user.email, "Linked", "c1", "user")
    deps.auth.authenticate.return_value = user
    deps.account.link_existing_account.return_value = linked_user
    assert deps.coordinator.link_google_with_password(resolved, "password") is linked_user
    deps.auth.authenticate.assert_called_once_with(resolved.email, "password")
    deps.account.link_existing_account.assert_called_once_with(
        resolution=resolved, authenticated_user=user,
    )
    deps.login.assert_called_once_with(linked_user)
    deps.account.register.assert_not_called()
    deps.identity.resolve.assert_not_called()


def test_link_invalid_password(deps, user):
    resolved = resolution(GoogleIdentityService.LINK_REQUIRED, user)
    deps.auth.authenticate.return_value = None
    assert deps.coordinator.link_google_with_password(resolved, "bad") is None
    deps.auth.authenticate.assert_called_once_with(resolved.email, "bad")
    deps.login.assert_not_called()
    deps.identity.resolve.assert_not_called()
    assert_no_account_calls(deps)


@pytest.mark.parametrize("status", ["linked", "registration_required", "unknown"])
def test_link_wrong_status(deps, status):
    with pytest.raises(ValueError):
        deps.coordinator.link_google_with_password(resolution(status), "password")
    deps.auth.authenticate.assert_not_called()
    deps.login.assert_not_called()
    deps.identity.resolve.assert_not_called()
    assert_no_account_calls(deps)


def test_default_session_login_is_lazy(deps, user, monkeypatch):
    coordinator = AuthenticationCoordinator(
        auth_service=deps.auth, google_identity_service=deps.identity,
        google_account_service=deps.account,
    )
    deps.auth.authenticate.return_value = user
    monkeypatch.setitem(sys.modules, "services.session_auth", SimpleNamespace(login_user=deps.login))
    assert coordinator.authenticate_with_password(user.email, "password") is user
    deps.login.assert_called_once_with(user)


def test_link_service_failure_does_not_create_session(deps, user):
    deps.auth.authenticate.return_value = user
    deps.account.link_existing_account.side_effect = ValueError("Rejected")
    with pytest.raises(ValueError):
        deps.coordinator.link_google_with_password(
            resolution(GoogleIdentityService.LINK_REQUIRED, user), "password",
        )
    deps.login.assert_not_called()
    deps.account.register.assert_not_called()


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError, Exception])
def test_registration_failure_is_translated_and_chained(deps, error_type):
    resolved = resolution(GoogleIdentityService.REGISTRATION_REQUIRED)
    deps.identity.resolve.return_value = resolved
    original = error_type("Private implementation details")
    deps.account.register.side_effect = original
    with pytest.raises(GoogleRegistrationError) as raised:
        deps.coordinator.authenticate_with_google({})
    assert raised.value.__cause__ is original
    assert not isinstance(raised.value, GoogleSessionError)
    assert "Private implementation details" not in str(raised.value)
    deps.account.register.assert_called_once_with(resolved)
    deps.login.assert_not_called()
    deps.auth.authenticate.assert_not_called()
    deps.account.link_existing_account.assert_not_called()


def test_identity_failure_is_not_translated(deps):
    original = ValueError("Invalid identity")
    deps.identity.resolve.side_effect = original
    with pytest.raises(ValueError) as raised:
        deps.coordinator.authenticate_with_google({})
    assert raised.value is original
    deps.login.assert_not_called()
    assert_no_account_calls(deps)


@pytest.mark.parametrize("status", ["linked", "registration_required"])
@pytest.mark.parametrize("error_type", [ValueError, RuntimeError, Exception])
def test_google_session_failure_is_translated_and_chained(deps, user, status, error_type):
    deps.identity.resolve.return_value = resolution(status, user)
    deps.account.register.return_value = user
    original = error_type("Private session implementation details")
    deps.login.side_effect = original
    with pytest.raises(GoogleSessionError) as raised:
        deps.coordinator.authenticate_with_google({})
    assert raised.value.__cause__ is original
    assert "Private session implementation details" not in str(raised.value)
    assert not isinstance(raised.value, GoogleRegistrationError)
    if status == "registration_required":
        deps.account.register.assert_called_once_with(deps.identity.resolve.return_value)
    else:
        deps.account.register.assert_not_called()
    deps.login.assert_called_once_with(user)
    deps.account.link_existing_account.assert_not_called()
