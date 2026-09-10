from services.active_user_session import (
    ACTIVE_USER_ID_KEY,
    ACTIVE_USER_OWNER_ID_KEY,
    ActiveUserSession,
)


def test_empty_state_returns_no_active_user():
    state = {}

    session = ActiveUserSession(
        state
    )

    active_user_id = (
        session.get_active_user_id(
            authenticated_user_id="user-a"
        )
    )

    assert active_user_id is None
    assert (
        state[ACTIVE_USER_OWNER_ID_KEY]
        == "user-a"
    )
    assert (
        ACTIVE_USER_ID_KEY
        not in state
    )


def test_active_user_persists_for_same_authenticated_user():
    state = {}

    session = ActiveUserSession(
        state
    )

    session.set_active_user_id(
        authenticated_user_id="admin-a",
        active_user_id="user-b",
    )

    active_user_id = (
        session.get_active_user_id(
            authenticated_user_id="admin-a"
        )
    )

    assert active_user_id == "user-b"


def test_active_user_is_cleared_when_authenticated_user_changes():
    state = {}

    session = ActiveUserSession(
        state
    )

    session.set_active_user_id(
        authenticated_user_id="admin-a",
        active_user_id="user-b",
    )

    active_user_id = (
        session.get_active_user_id(
            authenticated_user_id="user-c"
        )
    )

    assert active_user_id is None
    assert (
        state[ACTIVE_USER_OWNER_ID_KEY]
        == "user-c"
    )
    assert (
        ACTIVE_USER_ID_KEY
        not in state
    )


def test_reset_returns_context_to_authenticated_user():
    state = {}

    session = ActiveUserSession(
        state
    )

    session.set_active_user_id(
        authenticated_user_id="admin-a",
        active_user_id="user-b",
    )

    session.reset(
        authenticated_user_id="admin-a"
    )

    assert (
        session.get_active_user_id(
            authenticated_user_id="admin-a"
        )
        is None
    )


def test_empty_active_user_id_is_rejected():
    state = {}

    session = ActiveUserSession(
        state
    )

    try:
        session.set_active_user_id(
            authenticated_user_id="admin-a",
            active_user_id="   ",
        )
    except ValueError as error:
        assert (
            str(error)
            == "Active user id is required."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )
