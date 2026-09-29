from contextlib import contextmanager
from types import SimpleNamespace

from services import session_auth
from tests.test_session_auth_security import (
    AttrDict,
    FakeConnection,
    FakeCookies,
)


def _runtime(monkeypatch):
    connection = FakeConnection()
    cookies = FakeCookies()
    state = AttrDict()

    user = SimpleNamespace(
        id="user-cache-test",
        display_name="Cache Test",
    )

    context = SimpleNamespace(
        cursors=object()
    )

    connection_count = {
        "value": 0
    }

    @contextmanager
    def get_connection():
        connection_count["value"] += 1
        yield connection

    class Repository:
        def get_by_id(
            self,
            user_id,
        ):
            return (
                user
                if user_id == user.id
                else None
            )

    monkeypatch.setattr(
        session_auth,
        "get_script_run_ctx",
        lambda: context,
    )

    monkeypatch.setattr(
        session_auth,
        "_get_cookies",
        lambda: cookies,
    )

    monkeypatch.setattr(
        session_auth,
        "get_connection",
        get_connection,
    )

    monkeypatch.setattr(
        session_auth,
        "UserRepository",
        Repository,
    )

    monkeypatch.setattr(
        session_auth.st,
        "session_state",
        state,
    )

    return SimpleNamespace(
        connection=connection,
        cookies=cookies,
        state=state,
        user=user,
        context=context,
        connection_count=connection_count,
    )


def test_authenticated_user_is_validated_once_per_rerun(
    monkeypatch,
):
    runtime = _runtime(
        monkeypatch
    )

    session_auth.login_user(
        runtime.user
    )

    # Ignore the DB write used to create the session.
    runtime.connection_count[
        "value"
    ] = 0

    first = (
        session_auth.get_authenticated_user()
    )

    second = (
        session_auth.get_authenticated_user()
    )

    assert first is runtime.user
    assert second is runtime.user

    assert runtime.connection_count[
        "value"
    ] == 1


def test_new_rerun_revalidates_server_session(
    monkeypatch,
):
    runtime = _runtime(
        monkeypatch
    )

    session_auth.login_user(
        runtime.user
    )

    runtime.connection_count[
        "value"
    ] = 0

    assert (
        session_auth.get_authenticated_user()
        is runtime.user
    )

    assert runtime.connection_count[
        "value"
    ] == 1

    runtime.context.cursors = object()

    assert (
        session_auth.get_authenticated_user()
        is runtime.user
    )

    assert runtime.connection_count[
        "value"
    ] == 2


def test_logout_invalidates_same_rerun_auth_cache(
    monkeypatch,
):
    runtime = _runtime(
        monkeypatch
    )

    session_auth.login_user(
        runtime.user
    )

    assert (
        session_auth.get_authenticated_user()
        is runtime.user
    )

    session_auth.logout_user()

    assert (
        session_auth.get_authenticated_user()
        is None
    )


def test_revocation_invalidates_same_rerun_auth_cache(
    monkeypatch,
):
    runtime = _runtime(
        monkeypatch
    )

    session_auth.login_user(
        runtime.user
    )

    assert (
        session_auth.get_authenticated_user()
        is runtime.user
    )

    session_auth.revoke_user_sessions(
        runtime.user.id
    )

    assert (
        session_auth.get_authenticated_user()
        is None
    )
