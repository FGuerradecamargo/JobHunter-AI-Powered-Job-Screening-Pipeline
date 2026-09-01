from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest


# session_auth intentionally fails closed without this
# environment variable. Tests use a test-only value.
os.environ.setdefault(
    "SESSION_COOKIE_KEY",
    "test-only-session-cookie-key",
)

from services import session_auth


class AttrDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class FakeCookies(dict):
    def save(self):
        pass


class FakeCursor:
    def __init__(
        self,
        *,
        row=None,
        rowcount=0,
    ):
        self._row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self):
        self.sessions = {}

    def execute(
        self,
        sql,
        params=(),
    ):
        normalized = " ".join(
            sql.split()
        )

        if normalized.startswith(
            "CREATE TABLE IF NOT EXISTS "
            "user_sessions"
        ):
            return FakeCursor()

        if normalized.startswith(
            "INSERT INTO user_sessions"
        ):
            (
                token_hash,
                user_id,
                expires_at,
                created_at,
            ) = params

            self.sessions[token_hash] = {
                "user_id": user_id,
                "expires_at": expires_at,
                "created_at": created_at,
            }

            return FakeCursor(
                rowcount=1
            )

        if normalized.startswith(
            "DELETE FROM user_sessions"
        ):
            if "WHERE user_id = ?" in normalized:
                user_id = params[0]

                matching_tokens = [
                    token_hash
                    for (
                        token_hash,
                        stored,
                    ) in self.sessions.items()
                    if (
                        stored["user_id"]
                        == user_id
                    )
                ]

                for token_hash in matching_tokens:
                    self.sessions.pop(
                        token_hash,
                        None,
                    )

                return FakeCursor(
                    rowcount=len(
                        matching_tokens
                    )
                )

            token_hash = params[0]

            existed = (
                token_hash
                in self.sessions
            )

            self.sessions.pop(
                token_hash,
                None,
            )

            return FakeCursor(
                rowcount=(
                    1
                    if existed
                    else 0
                )
            )

        if (
            normalized.startswith("SELECT")
            and "FROM user_sessions"
            in normalized
            and "WHERE token = ?"
            in normalized
        ):
            token_hash = params[0]

            stored = self.sessions.get(
                token_hash
            )

            if stored is None:
                return FakeCursor(
                    row=None
                )

            return FakeCursor(
                row={
                    "user_id": (
                        stored["user_id"]
                    ),
                    "expires_at": (
                        stored["expires_at"]
                    ),
                }
            )

        raise AssertionError(
            f"Unexpected SQL: {normalized}"
        )


@pytest.fixture
def session_runtime(
    monkeypatch,
):
    connection = FakeConnection()
    cookies = FakeCookies()

    user = SimpleNamespace(
        id="user_test_1",
        display_name="Test User",
    )

    @contextmanager
    def fake_get_connection():
        yield connection

    class FakeUserRepository:
        def get_by_id(
            self,
            user_id,
        ):
            if user_id == user.id:
                return user

            return None

    fake_streamlit = SimpleNamespace(
        session_state=AttrDict()
    )

    monkeypatch.setattr(
        session_auth,
        "cookies",
        cookies,
    )

    monkeypatch.setattr(
        session_auth,
        "get_connection",
        fake_get_connection,
    )

    monkeypatch.setattr(
        session_auth,
        "UserRepository",
        FakeUserRepository,
    )

    monkeypatch.setattr(
        session_auth,
        "st",
        fake_streamlit,
    )

    return SimpleNamespace(
        connection=connection,
        cookies=cookies,
        user=user,
        streamlit=fake_streamlit,
    )


def test_session_token_hash_is_not_raw():
    raw_token = (
        "raw-session-token-example"
    )

    token_hash = (
        session_auth._hash_session_token(
            raw_token
        )
    )

    assert token_hash != raw_token
    assert len(token_hash) == 64

    assert token_hash == (
        session_auth._hash_session_token(
            raw_token
        )
    )


def test_empty_session_token_is_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "Session token cannot be empty"
        ),
    ):
        session_auth._hash_session_token(
            ""
        )


def test_login_lookup_and_logout_use_only_hash(
    session_runtime,
):
    runtime = session_runtime

    session_auth.login_user(
        runtime.user
    )

    raw_token = runtime.cookies[
        session_auth.SESSION_COOKIE
    ]

    token_hash = (
        session_auth._hash_session_token(
            raw_token
        )
    )

    assert raw_token
    assert raw_token != token_hash

    assert (
        raw_token
        not in runtime.connection.sessions
    )

    assert (
        token_hash
        in runtime.connection.sessions
    )

    runtime.streamlit.session_state.pop(
        "current_user",
        None,
    )

    resolved_user = (
        session_auth.get_current_user()
    )

    assert resolved_user is runtime.user

    session_auth.logout_user()

    assert (
        token_hash
        not in runtime.connection.sessions
    )

    assert (
        runtime.cookies[
            session_auth.SESSION_COOKIE
        ]
        == ""
    )


def test_hardcoded_beta_cookie_key_is_absent():
    source = Path(
        "services/session_auth.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "jobhunter-beta-cookie-key"
        not in source
    )

    assert (
        '"SESSION_COOKIE_KEY"'
        in source
    )


def test_revoked_database_session_invalidates_cached_user(
    session_runtime,
):
    runtime = session_runtime

    session_auth.login_user(
        runtime.user
    )

    raw_token = runtime.cookies[
        session_auth.SESSION_COOKIE
    ]

    token_hash = (
        session_auth._hash_session_token(
            raw_token
        )
    )

    assert (
        runtime.streamlit
        .session_state
        .current_user
        is runtime.user
    )

    # Simulate server-side revocation while the
    # Streamlit tab still has current_user cached.
    runtime.connection.sessions.pop(
        token_hash
    )

    resolved_user = (
        session_auth.get_current_user()
    )

    assert resolved_user is None

    assert (
        runtime.cookies[
            session_auth.SESSION_COOKIE
        ]
        == ""
    )

    assert (
        "current_user"
        not in runtime.streamlit.session_state
    )



def test_revoke_user_sessions_removes_all_sessions(
    session_runtime,
):
    runtime = session_runtime

    session_auth.login_user(
        runtime.user
    )

    first_raw_token = runtime.cookies[
        session_auth.SESSION_COOKIE
    ]

    first_hash = (
        session_auth._hash_session_token(
            first_raw_token
        )
    )

    session_auth.login_user(
        runtime.user
    )

    second_raw_token = runtime.cookies[
        session_auth.SESSION_COOKIE
    ]

    second_hash = (
        session_auth._hash_session_token(
            second_raw_token
        )
    )

    assert first_hash != second_hash

    assert first_hash in (
        runtime.connection.sessions
    )

    assert second_hash in (
        runtime.connection.sessions
    )

    revoked = (
        session_auth.revoke_user_sessions(
            runtime.user.id
        )
    )

    assert revoked == 2

    assert first_hash not in (
        runtime.connection.sessions
    )

    assert second_hash not in (
        runtime.connection.sessions
    )

    # Cached UI state alone must not keep
    # the revoked session authenticated.
    resolved_user = (
        session_auth.get_current_user()
    )

    assert resolved_user is None

    assert (
        runtime.cookies[
            session_auth.SESSION_COOKIE
        ]
        == ""
    )

    assert (
        "current_user"
        not in runtime.streamlit.session_state
    )


def test_revoke_user_sessions_requires_user_id():
    with pytest.raises(
        ValueError,
        match="User ID is required",
    ):
        session_auth.revoke_user_sessions(
            ""
        )
