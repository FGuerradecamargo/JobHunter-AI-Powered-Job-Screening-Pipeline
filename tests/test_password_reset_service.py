from __future__ import annotations

import sqlite3

import pytest

import services.database as database_module
import services.password_reset_service as password_reset_module
from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.auth_service import AuthService
from services.compromised_password_service import (
    CompromisedPasswordService,
)
from services.password_reset_service import (
    PasswordResetService,
)
from services.session_store import (
    ensure_session_table_with_connection,
)


@pytest.fixture(autouse=True)
def _disable_external_breach_lookup(
    monkeypatch,
):
    monkeypatch.setattr(
        CompromisedPasswordService,
        "is_compromised",
        classmethod(
            lambda cls, password: False
        ),
    )


def _open_database(database_file):
    connection = sqlite3.connect(
        database_file
    )
    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )
    return connection


def _prepare_database(
    monkeypatch,
    tmp_path,
):
    database_file = (
        tmp_path
        / "password-reset.db"
    )

    monkeypatch.delenv(
        "DATABASE_URL",
        raising=False,
    )

    monkeypatch.setattr(
        database_module,
        "DATABASE_FILE",
        database_file,
    )

    database_module.initialize_sqlite_database()

    old_password = (
        "original password value"
    )

    old_hash = (
        AuthService._build_password_hash(
            old_password,
            iterations=(
                AuthService.ITERATIONS
            ),
        )
    )

    connection = _open_database(
        database_file
    )

    try:
        connection.execute(
            """
            INSERT INTO users (
                id,
                email,
                display_name,
                candidate_id,
                access_level,
                password_hash,
                email_verified_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                "local-user",
                "local@example.com",
                "Local User",
                None,
                "user",
                old_hash,
                None,
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

        connection.execute(
            """
            INSERT INTO users (
                id,
                email,
                display_name,
                candidate_id,
                access_level,
                password_hash,
                email_verified_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                "no-password-user",
                "google@example.com",
                "No Password User",
                None,
                "user",
                None,
                None,
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

        ensure_session_table_with_connection(
            connection
        )

        connection.commit()

    finally:
        connection.close()

    return (
        database_file,
        old_password,
        old_hash,
    )


def test_reset_request_ignores_unknown_and_no_password_accounts(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    assert (
        PasswordResetService
        .request_reset_token(
            "missing@example.com"
        )
        is None
    )

    assert (
        PasswordResetService
        .request_reset_token(
            "google@example.com"
        )
        is None
    )


def test_reset_request_normalizes_email(
    monkeypatch,
    tmp_path,
):
    database_file, _, _ = (
        _prepare_database(
            monkeypatch,
            tmp_path,
        )
    )

    token = (
        PasswordResetService
        .request_reset_token(
            "  LOCAL@EXAMPLE.COM  "
        )
    )

    assert token is not None

    token_hash = (
        AccountActionTokenService
        .hash_token(token)
    )

    connection = _open_database(
        database_file
    )

    try:
        row = connection.execute(
            """
            SELECT
                user_id,
                token_hash
            FROM account_action_tokens
            WHERE purpose = ?
            """,
            (
                AccountActionTokenService
                .PASSWORD_RESET,
            ),
        ).fetchone()

        assert row is not None
        assert row["user_id"] == "local-user"
        assert row["token_hash"] == token_hash
        assert row["token_hash"] != token

    finally:
        connection.close()


def test_successful_reset_changes_password_revokes_sessions_and_is_one_time(
    monkeypatch,
    tmp_path,
):
    database_file, old_password, _ = (
        _prepare_database(
            monkeypatch,
            tmp_path,
        )
    )

    connection = _open_database(
        database_file
    )

    try:
        connection.executemany(
            """
            INSERT INTO user_sessions (
                token,
                user_id,
                expires_at,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    "session-hash-1",
                    "local-user",
                    "2099-01-01T00:00:00+00:00",
                    "2026-09-01T00:00:00+00:00",
                ),
                (
                    "session-hash-2",
                    "local-user",
                    "2099-01-01T00:00:00+00:00",
                    "2026-09-01T00:00:00+00:00",
                ),
            ],
        )

        connection.commit()

    finally:
        connection.close()

    token = (
        PasswordResetService
        .request_reset_token(
            "local@example.com"
        )
    )

    assert token is not None

    new_password = (
        "new secure password value"
    )

    assert (
        PasswordResetService
        .reset_password(
            token,
            new_password,
        )
        is True
    )

    # One-time token.
    assert (
        PasswordResetService
        .reset_password(
            token,
            "another secure password value",
        )
        is False
    )

    connection = _open_database(
        database_file
    )

    try:
        user = connection.execute(
            """
            SELECT password_hash
            FROM users
            WHERE id = ?
            """,
            ("local-user",),
        ).fetchone()

        assert user is not None

        assert AuthService.verify_password(
            new_password,
            user["password_hash"],
        )

        assert not AuthService.verify_password(
            old_password,
            user["password_hash"],
        )

        session_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM user_sessions
            WHERE user_id = ?
            """,
            ("local-user",),
        ).fetchone()["total"]

        assert session_count == 0

        action_token = connection.execute(
            """
            SELECT used_at
            FROM account_action_tokens
            WHERE token_hash = ?
            """,
            (
                AccountActionTokenService
                .hash_token(token),
            ),
        ).fetchone()

        assert action_token is not None
        assert action_token["used_at"] is not None

    finally:
        connection.close()


def test_invalid_new_password_does_not_burn_reset_token(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    token = (
        PasswordResetService
        .request_reset_token(
            "local@example.com"
        )
    )

    assert token is not None

    with pytest.raises(
        ValueError,
        match="at least 15 characters",
    ):
        PasswordResetService.reset_password(
            token,
            "too-short",
        )

    # The same recovery token must still work
    # because password validation happened first.
    assert (
        PasswordResetService
        .reset_password(
            token,
            "valid replacement password",
        )
        is True
    )


def test_reset_transaction_rolls_back_everything_on_failure(
    monkeypatch,
    tmp_path,
):
    database_file, _, old_hash = (
        _prepare_database(
            monkeypatch,
            tmp_path,
        )
    )

    connection = _open_database(
        database_file
    )

    try:
        connection.execute(
            """
            INSERT INTO user_sessions (
                token,
                user_id,
                expires_at,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "rollback-session",
                "local-user",
                "2099-01-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

        connection.commit()

    finally:
        connection.close()

    token = (
        PasswordResetService
        .request_reset_token(
            "local@example.com"
        )
    )

    assert token is not None

    token_hash = (
        AccountActionTokenService
        .hash_token(token)
    )

    original_revoke = (
        password_reset_module
        .revoke_user_sessions_with_connection
    )

    def fail_after_session_delete(
        connection,
        user_id,
    ):
        connection.execute(
            """
            DELETE FROM user_sessions
            WHERE user_id = ?
            """,
            (user_id,),
        )

        raise RuntimeError(
            "synthetic reset failure"
        )

    monkeypatch.setattr(
        password_reset_module,
        "revoke_user_sessions_with_connection",
        fail_after_session_delete,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic reset failure",
    ):
        PasswordResetService.reset_password(
            token,
            "new rollback test password",
        )

    connection = _open_database(
        database_file
    )

    try:
        user = connection.execute(
            """
            SELECT password_hash
            FROM users
            WHERE id = ?
            """,
            ("local-user",),
        ).fetchone()

        assert user is not None
        assert user["password_hash"] == old_hash

        token_row = connection.execute(
            """
            SELECT
                used_at,
                invalidated_at
            FROM account_action_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        assert token_row is not None
        assert token_row["used_at"] is None
        assert token_row["invalidated_at"] is None

        session_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM user_sessions
            WHERE user_id = ?
            """,
            ("local-user",),
        ).fetchone()["total"]

        assert session_count == 1

    finally:
        connection.close()

    # Restore the real revocation function before
    # proving that the rolled-back token still works.
    monkeypatch.setattr(
        password_reset_module,
        "revoke_user_sessions_with_connection",
        original_revoke,
    )

    # After rollback, the original token remains usable.
    assert (
        PasswordResetService
        .reset_password(
            token,
            "new rollback test password",
        )
        is True
    )
