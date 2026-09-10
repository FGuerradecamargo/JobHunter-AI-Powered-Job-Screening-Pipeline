from models.app_user import AppUser
from services.active_user_context_service import (
    ActiveUserContextService,
)
from services.active_user_session import (
    ActiveUserSession,
)


class FakeUserContextService:
    def __init__(
        self,
        *,
        target=None,
        fail_active=False,
    ):
        self.target = target
        self.fail_active = fail_active
        self.calls = []

    def resolve(
        self,
        *,
        authenticated_user,
        active_user_id=None,
    ):
        from models.user_context import UserContext

        self.calls.append(
            active_user_id
        )

        if (
            active_user_id
            and self.fail_active
        ):
            raise PermissionError(
                "User cannot change active account."
            )

        if active_user_id:
            if (
                self.target is None
                or self.target.id
                != active_user_id
            ):
                raise ValueError(
                    "Active user was not found."
                )

            return UserContext(
                authenticated_user=(
                    authenticated_user
                ),
                active_user=self.target,
            )

        return UserContext(
            authenticated_user=(
                authenticated_user
            ),
            active_user=authenticated_user,
        )


def _user(
    user_id,
    access_level="user",
):
    return AppUser(
        id=user_id,
        email=f"{user_id}@example.com",
        display_name=user_id,
        candidate_id=f"candidate-{user_id}",
        access_level=access_level,
    )


def test_resolve_defaults_to_authenticated_user():
    admin = _user(
        "admin-a",
        access_level="admin",
    )

    state = {}

    service = ActiveUserContextService(
        active_user_session=(
            ActiveUserSession(state)
        ),
        user_context_service=(
            FakeUserContextService()
        ),
    )

    context = service.resolve(
        authenticated_user=admin
    )

    assert context.active_user == admin


def test_valid_saved_active_user_is_resolved():
    admin = _user(
        "admin-a",
        access_level="admin",
    )

    target = _user(
        "user-b"
    )

    state = {}

    session = ActiveUserSession(
        state
    )

    session.set_active_user_id(
        authenticated_user_id=admin.id,
        active_user_id=target.id,
    )

    service = ActiveUserContextService(
        active_user_session=session,
        user_context_service=(
            FakeUserContextService(
                target=target
            )
        ),
    )

    context = service.resolve(
        authenticated_user=admin
    )

    assert context.active_user == target
    assert context.authenticated_user == admin


def test_invalid_saved_context_is_reset_to_self():
    admin = _user(
        "admin-a",
        access_level="admin",
    )

    state = {}

    session = ActiveUserSession(
        state
    )

    session.set_active_user_id(
        authenticated_user_id=admin.id,
        active_user_id="user-b",
    )

    fake_context = (
        FakeUserContextService(
            fail_active=True
        )
    )

    service = ActiveUserContextService(
        active_user_session=session,
        user_context_service=fake_context,
    )

    context = service.resolve(
        authenticated_user=admin
    )

    assert context.active_user == admin

    assert (
        session.get_active_user_id(
            authenticated_user_id=admin.id
        )
        is None
    )

    assert fake_context.calls == [
        "user-b",
        None,
    ]


def test_activate_validates_before_persisting():
    admin = _user(
        "admin-a",
        access_level="admin",
    )

    target = _user(
        "user-b"
    )

    state = {}

    session = ActiveUserSession(
        state
    )

    service = ActiveUserContextService(
        active_user_session=session,
        user_context_service=(
            FakeUserContextService(
                target=target
            )
        ),
    )

    context = service.activate(
        authenticated_user=admin,
        active_user_id=target.id,
    )

    assert context.active_user == target

    assert (
        session.get_active_user_id(
            authenticated_user_id=admin.id
        )
        == target.id
    )


def test_activate_self_clears_viewing_as():
    admin = _user(
        "admin-a",
        access_level="admin",
    )

    state = {}

    session = ActiveUserSession(
        state
    )

    session.set_active_user_id(
        authenticated_user_id=admin.id,
        active_user_id="user-b",
    )

    service = ActiveUserContextService(
        active_user_session=session,
        user_context_service=(
            FakeUserContextService()
        ),
    )

    context = service.activate(
        authenticated_user=admin,
        active_user_id=admin.id,
    )

    assert context.active_user == admin

    assert (
        session.get_active_user_id(
            authenticated_user_id=admin.id
        )
        is None
    )
