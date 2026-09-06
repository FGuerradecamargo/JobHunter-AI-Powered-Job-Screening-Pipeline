from __future__ import annotations

import sqlite3

import pytest

import services.database as database_module
from services.user_identity_repository import (
    UserIdentityRepository,
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
        / "user-identity-repository.db"
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
                "workpilot-user",
                "user@example.com",
                "WorkPilot User",
                None,
                "user",
                None,
                None,
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return database_file


def test_link_and_resolve_external_identity(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    repository = UserIdentityRepository()

    assert (
        repository.get_user_id(
            provider="google",
            subject="google-subject-1",
        )
        is None
    )

    repository.link(
        user_id="workpilot-user",
        provider=" Google ",
        subject="google-subject-1",
        provider_email=" USER@EXAMPLE.COM ",
    )

    assert (
        repository.get_user_id(
            provider="GOOGLE",
            subject="google-subject-1",
        )
        == "workpilot-user"
    )


def test_record_authentication_updates_identity_metadata(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    repository = UserIdentityRepository()

    repository.link(
        user_id="workpilot-user",
        provider="google",
        subject="google-subject-1",
        provider_email="old@example.com",
    )

    resolved_user_id = (
        repository.record_authentication(
            provider="google",
            subject="google-subject-1",
            provider_email="NEW@EXAMPLE.COM",
        )
    )

    assert (
        resolved_user_id
        == "workpilot-user"
    )

    connection = _open_database(
        database_file
    )

    try:
        row = connection.execute(
            """
            SELECT
                provider_email,
                last_authenticated_at
            FROM user_identities
            WHERE
                provider = ?
                AND subject = ?
            """,
            (
                "google",
                "google-subject-1",
            ),
        ).fetchone()

        assert row is not None
        assert (
            row["provider_email"]
            == "new@example.com"
        )
        assert (
            row["last_authenticated_at"]
            is not None
        )

    finally:
        connection.close()


def test_record_authentication_does_not_create_identity(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    repository = UserIdentityRepository()

    assert (
        repository.record_authentication(
            provider="google",
            subject="unknown-google-subject",
            provider_email="user@example.com",
        )
        is None
    )


@pytest.mark.parametrize(
    (
        "provider",
        "subject",
        "message",
    ),
    [
        (
            "",
            "subject",
            "Identity provider is required",
        ),
        (
            "google",
            "",
            "Identity subject is required",
        ),
    ],
)
def test_identity_lookup_validates_required_fields(
    monkeypatch,
    tmp_path,
    provider,
    subject,
    message,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    repository = UserIdentityRepository()

    with pytest.raises(
        ValueError,
        match=message,
    ):
        repository.get_user_id(
            provider=provider,
            subject=subject,
        )
