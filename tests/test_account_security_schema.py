from __future__ import annotations

import sqlite3

import pytest

import services.database as database_module


def _open_database(database_file):
    connection = sqlite3.connect(
        database_file
    )
    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )
    return connection


def test_existing_sqlite_users_gain_account_security_schema(
    monkeypatch,
    tmp_path,
):
    database_file = (
        tmp_path
        / "legacy-account-security.db"
    )

    connection = _open_database(
        database_file
    )

    try:
        # Simulate the pre-9B users schema.
        connection.execute(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                candidate_id TEXT UNIQUE,
                access_level TEXT
                    NOT NULL DEFAULT 'user',
                password_hash TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.commit()

    finally:
        connection.close()

    monkeypatch.delenv(
        "DATABASE_URL",
        raising=False,
    )

    monkeypatch.setattr(
        database_module,
        "DATABASE_FILE",
        database_file,
    )

    # Migration must work and be idempotent.
    database_module.initialize_sqlite_database()
    database_module.initialize_sqlite_database()

    connection = _open_database(
        database_file
    )

    try:
        user_columns = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA table_info(users)
                """
            ).fetchall()
        }

        assert (
            "email_verified_at"
            in user_columns
        )

        token_columns = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    account_action_tokens
                )
                """
            ).fetchall()
        }

        assert token_columns == {
            "id",
            "user_id",
            "purpose",
            "token_hash",
            "expires_at",
            "used_at",
            "invalidated_at",
            "created_at",
        }

        indexes = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA index_list(
                    account_action_tokens
                )
                """
            ).fetchall()
        }

        assert (
            "idx_account_action_tokens_user_purpose"
            in indexes
        )

        assert (
            "idx_account_action_tokens_expiry"
            in indexes
        )

    finally:
        connection.close()


def test_account_action_token_constraints(
    monkeypatch,
    tmp_path,
):
    database_file = (
        tmp_path
        / "account-token-constraints.db"
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
                "security-user",
                "security@example.com",
                "Security User",
                None,
                "user",
                None,
                None,
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

        connection.execute(
            """
            INSERT INTO account_action_tokens (
                id,
                user_id,
                purpose,
                token_hash,
                expires_at,
                used_at,
                invalidated_at,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                "token-1",
                "security-user",
                "password_reset",
                "hash-1",
                "2026-09-01T00:30:00+00:00",
                None,
                None,
                "2026-09-01T00:00:00+00:00",
            ),
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO account_action_tokens (
                    id,
                    user_id,
                    purpose,
                    token_hash,
                    expires_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "token-invalid-purpose",
                    "security-user",
                    "not_a_real_purpose",
                    "hash-invalid",
                    "2026-09-01T00:30:00+00:00",
                    "2026-09-01T00:00:00+00:00",
                ),
            )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO account_action_tokens (
                    id,
                    user_id,
                    purpose,
                    token_hash,
                    expires_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "token-duplicate-hash",
                    "security-user",
                    "email_verification",
                    "hash-1",
                    "2026-09-02T00:00:00+00:00",
                    "2026-09-01T00:00:00+00:00",
                ),
            )

        connection.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            ("security-user",),
        )

        remaining = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM account_action_tokens
            WHERE user_id = ?
            """,
            ("security-user",),
        ).fetchone()["total"]

        assert remaining == 0

    finally:
        connection.close()
