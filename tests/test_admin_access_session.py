import pytest

from services.admin_access_session import AdminAccessSession


def test_authorized_target_is_bound_to_authenticated_user():
    state = {}
    session = AdminAccessSession(state)

    session.authorize(
        authenticated_user_id="admin-a",
        target_user_id="user-b",
    )

    assert session.get_authorized_target(
        authenticated_user_id="admin-a"
    ) == "user-b"
    assert session.get_authorized_target(
        authenticated_user_id="admin-c"
    ) is None


def test_new_target_replaces_previous_grant():
    state = {}
    session = AdminAccessSession(state)

    session.authorize(
        authenticated_user_id="admin-a",
        target_user_id="user-b",
    )
    session.authorize(
        authenticated_user_id="admin-a",
        target_user_id="user-c",
    )

    assert session.get_authorized_target(
        authenticated_user_id="admin-a"
    ) == "user-c"


def test_reset_removes_authorized_target():
    state = {}
    session = AdminAccessSession(state)

    session.authorize(
        authenticated_user_id="admin-a",
        target_user_id="user-b",
    )
    session.reset(
        authenticated_user_id="admin-a"
    )

    assert session.get_authorized_target(
        authenticated_user_id="admin-a"
    ) is None


@pytest.mark.parametrize(
    "target_user_id",
    ["", "   ", "admin-a"],
)
def test_invalid_target_is_rejected(target_user_id):
    session = AdminAccessSession({})

    with pytest.raises(ValueError):
        session.authorize(
            authenticated_user_id="admin-a",
            target_user_id=target_user_id,
        )
