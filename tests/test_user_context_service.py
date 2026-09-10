from __future__ import annotations

import pytest

from models.app_user import AppUser
from services.user_context_service import (
    UserContextService,
)


class FakeUserRepository:
    def __init__(
        self,
        users=None,
    ):
        self.users = {
            user.id: user
            for user in (
                users or []
            )
        }

    def get_by_id(
        self,
        user_id,
    ):
        return self.users.get(
            user_id
        )


def _user(
    *,
    user_id,
    email,
    access_level="user",
):
    return AppUser(
        id=user_id,
        email=email,
        display_name=email,
        candidate_id=(
            f"candidate-{user_id}"
        ),
        access_level=access_level,
    )


def _service(
    users=None,
):
    service = UserContextService()
    service.user_repository = (
        FakeUserRepository(
            users=users
        )
    )
    return service


def test_normal_user_defaults_to_self():
    user = _user(
        user_id="user-a",
        email="a@example.com",
    )

    context = (
        _service()
        .resolve(
            authenticated_user=user
        )
    )

    assert (
        context.authenticated_user
        == user
    )
    assert (
        context.active_user
        == user
    )
    assert (
        context.is_viewing_as
        is False
    )


def test_normal_user_cannot_change_active_user():
    user = _user(
        user_id="user-a",
        email="a@example.com",
    )

    with pytest.raises(
        PermissionError,
        match=(
            "cannot change active account"
        ),
    ):
        (
            _service()
            .resolve(
                authenticated_user=user,
                active_user_id="user-b",
            )
        )


def test_admin_defaults_to_self():
    admin = _user(
        user_id="admin-a",
        email="admin@example.com",
        access_level="admin",
    )

    context = (
        _service()
        .resolve(
            authenticated_user=admin
        )
    )

    assert (
        context.authenticated_user
        == admin
    )
    assert (
        context.active_user
        == admin
    )
    assert (
        context.is_viewing_as
        is False
    )


def test_admin_can_change_active_user_without_changing_identity():
    admin = _user(
        user_id="admin-a",
        email="admin@example.com",
        access_level="admin",
    )

    target = _user(
        user_id="user-b",
        email="b@example.com",
    )

    context = (
        _service(
            users=[
                target,
            ]
        )
        .resolve(
            authenticated_user=admin,
            active_user_id=target.id,
        )
    )

    assert (
        context.authenticated_user
        == admin
    )
    assert (
        context.active_user
        == target
    )
    assert (
        context.authenticated_user
        != context.active_user
    )
    assert (
        context.is_viewing_as
        is True
    )


def test_admin_cannot_activate_missing_user():
    admin = _user(
        user_id="admin-a",
        email="admin@example.com",
        access_level="admin",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Active user was not found"
        ),
    ):
        (
            _service()
            .resolve(
                authenticated_user=admin,
                active_user_id="missing-user",
            )
        )
