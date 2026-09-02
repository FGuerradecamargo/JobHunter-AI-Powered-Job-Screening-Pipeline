from __future__ import annotations

import sqlite3

import services.database as database_module
from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.email_verification_delivery_service import (
    EmailVerificationDeliveryService,
)
from services.public_url_service import (
    PublicUrlConfigurationError,
    PublicUrlService,
)
from services.transactional_email_service import (
    TransactionalEmailError,
    TransactionalEmailService,
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
        / "email-verification-delivery.db"
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
                "owner@example.com",
                "Owner",
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
                "Verified",
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


def test_sends_verification_to_email_owned_by_user(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    captured = {}

    monkeypatch.setattr(
        PublicUrlService,
        "email_verification_url",
        classmethod(
            lambda cls, token: (
                "https://workpilot.example"
                f"/verify-email?token={token}"
            )
        ),
    )

    def fake_send_email(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        fake_send_email,
    )

    assert (
        EmailVerificationDeliveryService
        .send_verification_email(
            "unverified-user"
        )
        is True
    )

    assert (
        captured["to_email"]
        == "owner@example.com"
    )

    assert (
        captured["subject"]
        == "Verify your WorkPilot email"
    )

    assert (
        "24 hours"
        in captured["html"]
    )

    token_rows = []

    with database_module.get_connection() as connection:
        token_rows = connection.execute(
            """
            SELECT token_hash
            FROM account_action_tokens
            WHERE
                user_id = ?
                AND purpose = ?
            """,
            (
                "unverified-user",
                AccountActionTokenService
                .EMAIL_VERIFICATION,
            ),
        ).fetchall()

    assert len(token_rows) == 1

    stored_hash = token_rows[0][
        "token_hash"
    ]

    assert (
        captured["idempotency_key"]
        == (
            "email-verification-"
            f"{stored_hash}"
        )
    )

    assert (
        stored_hash
        not in captured["html"]
    )


def test_verified_user_does_not_receive_email(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    def must_not_send(**kwargs):
        raise AssertionError(
            "Verified user must not "
            "receive verification email."
        )

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        must_not_send,
    )

    assert (
        EmailVerificationDeliveryService
        .send_verification_email(
            "verified-user"
        )
        is False
    )


def test_public_url_failure_does_not_send_email(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    def fail_url(
        cls,
        token,
    ):
        raise PublicUrlConfigurationError(
            "private URL detail"
        )

    monkeypatch.setattr(
        PublicUrlService,
        "email_verification_url",
        classmethod(fail_url),
    )

    def must_not_send(**kwargs):
        raise AssertionError(
            "Email must not be sent "
            "without a valid URL."
        )

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        must_not_send,
    )

    assert (
        EmailVerificationDeliveryService
        .send_verification_email(
            "unverified-user"
        )
        is False
    )


def test_provider_failure_is_contained(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.setattr(
        PublicUrlService,
        "email_verification_url",
        classmethod(
            lambda cls, token: (
                "https://workpilot.example"
                f"/verify-email?token={token}"
            )
        ),
    )

    def fail_send(**kwargs):
        raise TransactionalEmailError(
            "private provider detail"
        )

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        fail_send,
    )

    assert (
        EmailVerificationDeliveryService
        .send_verification_email(
            "unverified-user"
        )
        is False
    )
