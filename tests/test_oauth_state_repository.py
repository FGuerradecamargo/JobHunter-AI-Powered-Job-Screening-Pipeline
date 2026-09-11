from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import services.database as database_module
import services.oauth_state_repository as oauth_state_module
from services.oauth_state_repository import OAuthStateRepository


class FakeCursor:
    def __init__(self, *, row=None, rowcount=0):
        self._row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self):
        self.states = {}

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())

        if normalized.startswith(
            "INSERT INTO oauth_authorization_states"
        ):
            (
                state,
                user_id,
                initiated_by_user_id,
                code_verifier,
                created_at,
            ) = params

            self.states[state] = {
                "state": state,
                "user_id": user_id,
                "initiated_by_user_id": initiated_by_user_id,
                "code_verifier": code_verifier,
                "created_at": created_at,
                "consumed_at": None,
            }

            return FakeCursor(rowcount=1)

        if normalized.startswith(
            "SELECT state, code_verifier, user_id, "
            "initiated_by_user_id, created_at, consumed_at "
            "FROM oauth_authorization_states"
        ):
            return FakeCursor(
                row=self.states.get(params[0])
            )

        if normalized.startswith(
            "UPDATE oauth_authorization_states "
            "SET consumed_at"
        ):
            consumed_at, state = params
            stored = self.states.get(state)

            if stored is None:
                return FakeCursor(rowcount=0)

            stored["consumed_at"] = consumed_at
            return FakeCursor(rowcount=1)

        raise AssertionError(
            f"Unexpected OAuth state query: {normalized}"
        )


def test_oauth_state_is_bound_to_initiating_identity(
    monkeypatch,
):
    connection = FakeConnection()

    @contextmanager
    def fake_get_connection():
        yield connection

    monkeypatch.setattr(
        oauth_state_module,
        "get_connection",
        fake_get_connection,
    )

    repository = OAuthStateRepository()

    repository.save(
        state="state-a",
        user_id="user-b",
        initiated_by_user_id="admin-a",
        code_verifier="verifier-a",
    )

    assert (
        repository.consume(
            "state-a",
            initiated_by_user_id="user-b",
        )
        is None
    )

    authorized_state = repository.consume(
        "state-a",
        initiated_by_user_id="admin-a",
    )

    assert authorized_state is not None
    assert authorized_state.user_id == "user-b"
    assert (
        authorized_state.initiated_by_user_id
        == "admin-a"
    )
    assert authorized_state.code_verifier == "verifier-a"

    assert (
        repository.consume(
            "state-a",
            initiated_by_user_id="admin-a",
        )
        is None
    )


def test_sqlite_schema_migrates_existing_oauth_state_table(
    monkeypatch,
    tmp_path,
):
    database_file = tmp_path / "legacy-oauth-state.db"

    connection = sqlite3.connect(database_file)

    try:
        connection.execute(
            """
            CREATE TABLE oauth_authorization_states (
                state TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                code_verifier TEXT NOT NULL,
                created_at TEXT NOT NULL,
                consumed_at TEXT
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        database_module,
        "DATABASE_FILE",
        database_file,
    )

    database_module.initialize_sqlite_database()

    connection = sqlite3.connect(database_file)

    try:
        columns = connection.execute(
            """
            PRAGMA table_info(oauth_authorization_states)
            """
        ).fetchall()
    finally:
        connection.close()

    assert "initiated_by_user_id" in {
        column[1]
        for column in columns
    }
