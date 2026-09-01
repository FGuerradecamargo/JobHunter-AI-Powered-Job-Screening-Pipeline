from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

import services.database as database_module
from services.account_action_token_service import (
    AccountActionTokenService,
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
        / "account-action-token.db"
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
                "token-user",
                "token-user@example.com",
                "Token User",
                None,
                "user",
                None,
                None,
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return database_file


def _load_tokens(
    database_file,
):
    connection = _open_database(
        database_file
    )

    try:
        return connection.execute(
            """
            SELECT
                id,
                user_id,
                purpose,
                token_hash,
                expires_at,
                used_at,
                invalidated_at,
                created_at
            FROM account_action_tokens
            ORDER BY created_at ASC
            """
        ).fetchall()

    finally:
        connection.close()


def test_password_reset_token_is_hashed_at_rest(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    raw_token = (
        AccountActionTokenService.issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    rows = _load_tokens(
        database_file
    )

    assert len(rows) == 1

    row = rows[0]

    assert raw_token
    assert len(raw_token) >= 48

    assert (
        row["token_hash"]
        == AccountActionTokenService
        .hash_token(raw_token)
    )

    assert (
        row["token_hash"]
        != raw_token
    )

    # The raw secret must not appear in any
    # persisted token field.
    assert raw_token not in {
        str(value)
        for value in row
        if value is not None
    }

    created_at = (
        database_module.datetime
        .fromisoformat(
            row["created_at"]
        )
    )

    expires_at = (
        database_module.datetime
        .fromisoformat(
            row["expires_at"]
        )
    )

    assert (
        expires_at - created_at
        == timedelta(minutes=30)
    )


def test_email_verification_token_has_24_hour_ttl(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .EMAIL_VERIFICATION
            ),
        )
    )

    row = _load_tokens(
        database_file
    )[0]

    created_at = (
        database_module.datetime
        .fromisoformat(
            row["created_at"]
        )
    )

    expires_at = (
        database_module.datetime
        .fromisoformat(
            row["expires_at"]
        )
    )

    assert (
        expires_at - created_at
        == timedelta(hours=24)
    )


def test_reissuing_same_purpose_invalidates_previous_token(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    first_raw = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    second_raw = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    assert first_raw != second_raw

    rows = _load_tokens(
        database_file
    )

    assert len(rows) == 2

    first = rows[0]
    second = rows[1]

    assert (
        first["invalidated_at"]
        is not None
    )

    assert (
        second["invalidated_at"]
        is None
    )

    assert first["used_at"] is None
    assert second["used_at"] is None


def test_different_purposes_remain_independently_active(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .EMAIL_VERIFICATION
            ),
        )
    )

    rows = _load_tokens(
        database_file
    )

    assert len(rows) == 2

    assert all(
        row["invalidated_at"] is None
        for row in rows
    )


def test_invalid_token_purpose_is_rejected(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="Invalid account action token purpose",
    ):
        (
            AccountActionTokenService
            .issue_token(
                user_id="token-user",
                purpose="invalid-purpose",
            )
        )



def test_valid_token_can_only_be_consumed_once(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    token = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    first_result = (
        AccountActionTokenService
        .consume_token(
            token=token,
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    second_result = (
        AccountActionTokenService
        .consume_token(
            token=token,
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    assert first_result == "token-user"
    assert second_result is None


def test_wrong_purpose_does_not_consume_token(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    token = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    wrong_result = (
        AccountActionTokenService
        .consume_token(
            token=token,
            purpose=(
                AccountActionTokenService
                .EMAIL_VERIFICATION
            ),
        )
    )

    assert wrong_result is None

    # The failed wrong-purpose attempt must
    # not destroy the real token.
    correct_result = (
        AccountActionTokenService
        .consume_token(
            token=token,
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    assert correct_result == "token-user"


def test_expired_token_cannot_be_consumed(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    token = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    token_hash = (
        AccountActionTokenService
        .hash_token(token)
    )

    connection = _open_database(
        database_file
    )

    try:
        connection.execute(
            """
            UPDATE account_action_tokens
            SET expires_at = ?
            WHERE token_hash = ?
            """,
            (
                "2000-01-01T00:00:00+00:00",
                token_hash,
            ),
        )

        connection.commit()

    finally:
        connection.close()

    result = (
        AccountActionTokenService
        .consume_token(
            token=token,
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    assert result is None


def test_invalidated_token_cannot_be_consumed(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    first_token = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    second_token = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    assert (
        AccountActionTokenService
        .consume_token(
            token=first_token,
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
        is None
    )

    assert (
        AccountActionTokenService
        .consume_token(
            token=second_token,
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
        == "token-user"
    )


def test_concurrent_consumption_has_exactly_one_winner(
    monkeypatch,
    tmp_path,
):
    from concurrent.futures import (
        ThreadPoolExecutor,
    )
    from threading import Barrier

    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    token = (
        AccountActionTokenService
        .issue_token(
            user_id="token-user",
            purpose=(
                AccountActionTokenService
                .PASSWORD_RESET
            ),
        )
    )

    barrier = Barrier(2)

    def consume():
        barrier.wait()

        return (
            AccountActionTokenService
            .consume_token(
                token=token,
                purpose=(
                    AccountActionTokenService
                    .PASSWORD_RESET
                ),
            )
        )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(consume)
            for _ in range(2)
        ]

        results = [
            future.result()
            for future in futures
        ]

    assert results.count(
        "token-user"
    ) == 1

    assert results.count(
        None
    ) == 1
