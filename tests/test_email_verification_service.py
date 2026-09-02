from __future__ import annotations

import sqlite3

import pytest

import services.database as database_module
from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.email_verification_service import (
    EmailVerificationService,
)


def _open_database(
    database_file,
):
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
        / "email-verification.db"
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "unverified-user",
                "new@example.com",
                "New User",
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "verified-user",
                "verified@example.com",
                "Verified User",
                None,
                "user",
                None,
                "2026-09-01T01:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T01:00:00+00:00",
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return database_file


def test_unverified_user_can_receive_verification_token(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    token = (
        EmailVerificationService
        .issue_verification_token(
            "unverified-user"
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
                purpose,
                token_hash
            FROM account_action_tokens
            WHERE token_hash = ?
            """,
            (
                token_hash,
            ),
        ).fetchone()

        assert row is not None
        assert (
            row["user_id"]
            == "unverified-user"
        )
        assert (
            row["purpose"]
            == AccountActionTokenService
            .EMAIL_VERIFICATION
        )
        assert row["token_hash"] != token

    finally:
        connection.close()


def test_verified_user_does_not_receive_new_token(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    assert (
        EmailVerificationService
        .issue_verification_token(
            "verified-user"
        )
        is None
    )


def test_unknown_user_is_rejected(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="User not found",
    ):
        (
            EmailVerificationService
            .issue_verification_token(
                "missing-user"
            )
        )


def test_successful_verification_marks_email_and_is_one_time(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    token = (
        EmailVerificationService
        .issue_verification_token(
            "unverified-user"
        )
    )

    assert token is not None

    assert (
        EmailVerificationService
        .verify_email(token)
        is True
    )

    assert (
        EmailVerificationService
        .verify_email(token)
        is False
    )

    connection = _open_database(
        database_file
    )

    try:
        user = connection.execute(
            """
            SELECT email_verified_at
            FROM users
            WHERE id = ?
            """,
            (
                "unverified-user",
            ),
        ).fetchone()

        assert user is not None
        assert (
            user["email_verified_at"]
            is not None
        )

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
        assert (
            action_token["used_at"]
            is not None
        )

    finally:
        connection.close()


def test_invalid_token_does_not_verify_email(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    assert (
        EmailVerificationService
        .verify_email(
            "invalid-verification-token"
        )
        is False
    )

    connection = _open_database(
        database_file
    )

    try:
        row = connection.execute(
            """
            SELECT email_verified_at
            FROM users
            WHERE id = ?
            """,
            (
                "unverified-user",
            ),
        ).fetchone()

        assert row is not None
        assert (
            row["email_verified_at"]
            is None
        )

    finally:
        connection.close()
