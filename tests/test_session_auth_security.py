from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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


@pytest.mark.parametrize('reuse', [False, True])
def test_logout_render_reuses_only_explicit_current_render_user(monkeypatch, reuse):
    from contextlib import nullcontext
    from unittest.mock import Mock
    user = SimpleNamespace(display_name='Synthetic')
    resolve = Mock(return_value=user)
    monkeypatch.setattr(session_auth, 'get_authenticated_user', resolve)
    caption = Mock()
    monkeypatch.setattr(session_auth, 'st', SimpleNamespace(
        sidebar=nullcontext(), caption=caption, button=lambda *a, **kw: False))
    session_auth.render_logout_button(**({'authenticated_user': user} if reuse else {}))
    assert resolve.call_count == (0 if reuse else 1)
    caption.assert_called_once_with('Signed in as Synthetic')


class FakeCookies(dict):
    def save(self):
        pass


class FakeCursor:
    def __init__(
        self,
        *,
        row=None,
        rows=None,
        rowcount=0,
    ):
        self._row = row
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


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

        if normalized == "PRAGMA table_info(user_sessions)":
            return FakeCursor(rows=[
                (0, "token"),
                (1, "user_id"),
                (2, "expires_at"),
                (3, "created_at"),
                (4, "last_activity_at"),
            ])

        if normalized.startswith(
            "UPDATE user_sessions SET last_activity_at = created_at"
        ):
            for stored in self.sessions.values():
                if not stored.get("last_activity_at"):
                    stored["last_activity_at"] = stored["created_at"]
            return FakeCursor()

        if normalized.startswith(
            "INSERT INTO user_sessions"
        ):
            (
                token_hash,
                user_id,
                expires_at,
                created_at,
                last_activity_at,
            ) = params

            self.sessions[token_hash] = {
                "user_id": user_id,
                "expires_at": expires_at,
                "created_at": created_at,
                "last_activity_at": last_activity_at,
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
                    "created_at": stored["created_at"],
                    "last_activity_at": stored["last_activity_at"],
                }
            )

        if normalized.startswith(
            "UPDATE user_sessions SET last_activity_at = ?"
        ):
            activity_at, token_hash = params
            stored = self.sessions.get(token_hash)
            if stored is not None:
                stored["last_activity_at"] = activity_at
            return FakeCursor(rowcount=int(stored is not None))

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


def test_expiration_clears_admin_access_and_requires_reauthentication(session_runtime):
    state = session_runtime.streamlit.session_state
    state["admin_access_granted"] = True
    state["admin_viewing_as_target"] = "other-user"
    session_auth._expire_local_session()
    assert "admin_access_granted" not in state
    assert "admin_viewing_as_target" not in state
    assert state["reauthentication_required"] is True


def test_failed_session_commit_does_not_publish_cookie(monkeypatch, session_runtime):
    @contextmanager
    def failed_connection():
        yield session_runtime.connection
        raise RuntimeError("simulated commit rejection")

    monkeypatch.setattr(session_auth, "ensure_session_table", lambda: None)
    monkeypatch.setattr(session_auth, "get_connection", failed_connection)
    with pytest.raises(RuntimeError):
        session_auth.login_user(session_runtime.user)
    assert not session_runtime.cookies.get(session_auth.SESSION_COOKIE)
    assert "current_user" not in session_runtime.streamlit.session_state


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


def _login_at(
    monkeypatch,
    runtime,
    now,
):
    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: now,
    )
    session_auth.login_user(runtime.user)
    raw_token = runtime.cookies[
        session_auth.SESSION_COOKIE
    ]
    return session_auth._hash_session_token(raw_token)


def test_session_is_valid_at_59_minutes_idle(
    monkeypatch,
    session_runtime,
):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token_hash = _login_at(
        monkeypatch,
        session_runtime,
        started_at,
    )
    checked_at = started_at + timedelta(minutes=59)
    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: checked_at,
    )

    assert session_auth.get_authenticated_user() is session_runtime.user
    assert (
        session_runtime.connection.sessions[token_hash]["last_activity_at"]
        == checked_at.isoformat()
    )


def test_session_is_valid_at_exactly_60_minutes_idle(
    monkeypatch,
    session_runtime,
):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _login_at(monkeypatch, session_runtime, started_at)
    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: started_at + timedelta(minutes=60),
    )

    assert session_auth.get_authenticated_user() is session_runtime.user


def test_idle_expired_session_is_revoked_and_cannot_be_revived(
    monkeypatch,
    session_runtime,
):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token_hash = _login_at(
        monkeypatch,
        session_runtime,
        started_at,
    )
    stale_cookie = session_runtime.cookies[session_auth.SESSION_COOKIE]
    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: started_at + timedelta(minutes=60, seconds=1),
    )

    assert session_auth.get_authenticated_user() is None
    assert token_hash not in session_runtime.connection.sessions
    assert session_runtime.cookies[session_auth.SESSION_COOKIE] == ""
    assert "current_user" not in session_runtime.streamlit.session_state
    assert (
        session_runtime.streamlit.session_state["authentication_notice"]
        == session_auth.SESSION_EXPIRED_NOTICE
    )

    session_runtime.cookies[session_auth.SESSION_COOKIE] = stale_cookie
    assert session_auth.get_authenticated_user() is None
    assert session_runtime.cookies[session_auth.SESSION_COOKIE] == ""


def test_activity_does_not_extend_absolute_expiration(
    monkeypatch,
    session_runtime,
):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token_hash = _login_at(
        monkeypatch,
        session_runtime,
        started_at,
    )
    original_expiry = session_runtime.connection.sessions[
        token_hash
    ]["expires_at"]
    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: started_at + timedelta(minutes=30),
    )

    assert session_auth.get_authenticated_user() is session_runtime.user
    assert (
        session_runtime.connection.sessions[token_hash]["expires_at"]
        == original_expiry
    )


def test_absolute_expiry_wins_with_recent_activity(
    monkeypatch,
    session_runtime,
):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token_hash = _login_at(
        monkeypatch,
        session_runtime,
        started_at,
    )
    absolute_expiry = started_at + timedelta(days=session_auth.SESSION_DAYS)
    session_runtime.connection.sessions[token_hash]["last_activity_at"] = (
        absolute_expiry - timedelta(minutes=1)
    ).isoformat()
    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: absolute_expiry,
    )

    assert session_auth.get_authenticated_user() is None
    assert token_hash not in session_runtime.connection.sessions


def test_activity_in_one_tab_keeps_same_token_valid(
    monkeypatch,
    session_runtime,
):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _login_at(monkeypatch, session_runtime, started_at)

    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: started_at + timedelta(minutes=59),
    )
    assert session_auth.get_authenticated_user() is session_runtime.user

    monkeypatch.setattr(
        session_auth,
        "_utc_now_datetime",
        lambda: started_at + timedelta(minutes=118),
    )
    assert session_auth.get_authenticated_user() is session_runtime.user


def test_legacy_session_activity_migrates_from_created_at(
    monkeypatch,
    tmp_path,
):
    import sqlite3
    from services import session_store

    database_file = tmp_path / "legacy-session.db"
    created_at = "2026-01-01T00:00:00+00:00"
    with sqlite3.connect(database_file) as connection:
        connection.execute(
            "CREATE TABLE users (id TEXT PRIMARY KEY)"
        )
        connection.execute(
            """
            CREATE TABLE user_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO users (id) VALUES (?)",
            ("user-1",),
        )
        connection.execute(
            "INSERT INTO user_sessions VALUES (?, ?, ?, ?)",
            (
                "token-hash",
                "user-1",
                "2026-01-08T00:00:00+00:00",
                created_at,
            ),
        )
        monkeypatch.setattr(session_store, "is_postgres", lambda: False)
        session_store.ensure_session_table_with_connection(connection)
        row = connection.execute(
            "SELECT last_activity_at FROM user_sessions"
        ).fetchone()

    assert row[0] == created_at


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


def test_session_cookie_key_prefers_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "SESSION_COOKIE_KEY",
        "  environment-key  ",
    )
    monkeypatch.setattr(
        session_auth.st,
        "secrets",
        {"SESSION_COOKIE_KEY": "streamlit-key"},
    )

    assert (
        session_auth._resolve_session_cookie_key()
        == "environment-key"
    )


def test_session_cookie_key_falls_back_to_streamlit_secrets(
    monkeypatch,
):
    monkeypatch.delenv(
        "SESSION_COOKIE_KEY",
        raising=False,
    )
    monkeypatch.setattr(
        session_auth.st,
        "secrets",
        {"SESSION_COOKIE_KEY": "  streamlit-key  "},
    )

    assert (
        session_auth._resolve_session_cookie_key()
        == "streamlit-key"
    )


def test_session_cookie_key_fails_closed_when_missing(
    monkeypatch,
):
    monkeypatch.delenv(
        "SESSION_COOKIE_KEY",
        raising=False,
    )
    monkeypatch.setattr(
        session_auth.st,
        "secrets",
        {},
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "^SESSION_COOKIE_KEY is not configured\\.$"
        ),
    ):
        session_auth._resolve_session_cookie_key()


def test_blank_session_cookie_key_values_are_missing(
    monkeypatch,
):
    monkeypatch.setenv(
        "SESSION_COOKIE_KEY",
        "   ",
    )
    monkeypatch.setattr(
        session_auth.st,
        "secrets",
        {"SESSION_COOKIE_KEY": "\t\n"},
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "^SESSION_COOKIE_KEY is not configured\\.$"
        ),
    ):
        session_auth._resolve_session_cookie_key()


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


def test_logout_clears_operational_and_impersonation_state(
    session_runtime,
):
    runtime = session_runtime

    session_auth.login_user(
        runtime.user
    )

    runtime.streamlit.session_state[
        "active_user_id"
    ] = "other-user"

    runtime.streamlit.session_state[
        "active_user_owner_id"
    ] = runtime.user.id

    runtime.streamlit.session_state[
        f"admin_viewing_as_{runtime.user.id}"
    ] = "other-user"

    runtime.streamlit.session_state[
        f"admin_access_open_{runtime.user.id}"
    ] = True

    runtime.streamlit.session_state[
        f"admin_access_target_{runtime.user.id}"
    ] = "other-user"

    runtime.streamlit.session_state[
        "unrelated_cached_state"
    ] = "value"

    session_auth.logout_user()

    assert (
        "current_user"
        not in runtime.streamlit.session_state
    )

    assert (
        "active_user_id"
        not in runtime.streamlit.session_state
    )

    assert (
        "active_user_owner_id"
        not in runtime.streamlit.session_state
    )

    assert (
        f"admin_viewing_as_{runtime.user.id}"
        not in runtime.streamlit.session_state
    )

    assert not any(
        str(key).startswith("admin_access_")
        for key in runtime.streamlit.session_state
    )

    assert (
        runtime.streamlit.session_state[
            "unrelated_cached_state"
        ]
        == "value"
    )
