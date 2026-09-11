from models.app_user import AppUser
from services.admin_reauthentication_service import (
    AdminReauthenticationService,
)


class FakeAuthService:
    def __init__(self, resolved_user=None):
        self.resolved_user = resolved_user
        self.calls = []

    def authenticate(self, email, password):
        self.calls.append((email, password))
        return self.resolved_user


def _user(
    user_id: str,
    *,
    access_level: str = "admin",
) -> AppUser:
    return AppUser(
        id=user_id,
        email=f"{user_id}@example.com",
        display_name=user_id,
        access_level=access_level,
    )


def test_admin_is_reauthenticated_by_own_email():
    admin = _user("admin-a")
    auth_service = FakeAuthService(admin)
    service = AdminReauthenticationService(
        auth_service=auth_service
    )

    assert service.reauthenticate(
        authenticated_user=admin,
        password="secret",
    )
    assert auth_service.calls == [
        (admin.email, "secret")
    ]


def test_invalid_password_does_not_grant_access():
    admin = _user("admin-a")
    service = AdminReauthenticationService(
        auth_service=FakeAuthService()
    )

    assert not service.reauthenticate(
        authenticated_user=admin,
        password="wrong",
    )


def test_different_resolved_identity_does_not_grant_access():
    admin = _user("admin-a")
    other_admin = _user("admin-b")
    service = AdminReauthenticationService(
        auth_service=FakeAuthService(other_admin)
    )

    assert not service.reauthenticate(
        authenticated_user=admin,
        password="secret",
    )


def test_non_admin_is_rejected_without_authentication():
    user = _user(
        "user-a",
        access_level="user",
    )
    auth_service = FakeAuthService(user)
    service = AdminReauthenticationService(
        auth_service=auth_service
    )

    assert not service.reauthenticate(
        authenticated_user=user,
        password="secret",
    )
    assert auth_service.calls == []


def test_lost_admin_privilege_does_not_grant_access():
    session_admin = _user("admin-a")
    refreshed_user = _user(
        "admin-a",
        access_level="user",
    )
    service = AdminReauthenticationService(
        auth_service=FakeAuthService(refreshed_user)
    )

    assert not service.reauthenticate(
        authenticated_user=session_admin,
        password="secret",
    )
