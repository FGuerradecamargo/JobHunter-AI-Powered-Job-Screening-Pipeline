from __future__ import annotations

import sqlite3

import pytest

from models.app_user import AppUser
import services.database as database_module
from services.google_account_service import (
    GoogleAccountService,
)
from services.google_identity_service import (
    GoogleIdentityResolution,
    GoogleIdentityService,
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
        / "google-account-service.db"
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

    return database_file


def _registration_resolution(
    *,
    subject="google-subject-new",
    email="google@example.com",
    display_name="Google User",
):
    return GoogleIdentityResolution(
        status=(
            GoogleIdentityService
            .REGISTRATION_REQUIRED
        ),
        subject=subject,
        email=email,
        display_name=display_name,
        user=None,
    )


def test_google_registration_creates_complete_account(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    service = GoogleAccountService()

    user = service.register(
        _registration_resolution()
    )

    assert (
        user.email
        == "google@example.com"
    )
    assert (
        user.display_name
        == "Google User"
    )
    assert user.candidate_id is not None
    assert user.access_level == "user"

    connection = _open_database(
        database_file
    )

    try:
        user_row = connection.execute(
            """
            SELECT
                id,
                candidate_id,
                password_hash,
                email_verified_at
            FROM users
            WHERE id = ?
            """,
            (
                user.id,
            ),
        ).fetchone()

        assert user_row is not None
        assert (
            user_row["candidate_id"]
            == user.candidate_id
        )
        assert (
            user_row["password_hash"]
            is None
        )
        assert (
            user_row["email_verified_at"]
            is not None
        )

        candidate_row = connection.execute(
            """
            SELECT
                name,
                "current_role",
                current_level,
                professional_summary
            FROM candidates
            WHERE id = ?
            """,
            (
                user.candidate_id,
            ),
        ).fetchone()

        assert candidate_row is not None
        assert (
            candidate_row["name"]
            == "Google User"
        )
        assert (
            candidate_row["current_role"]
            == ""
        )
        assert (
            candidate_row["current_level"]
            == ""
        )
        assert (
            candidate_row["professional_summary"]
            == ""
        )

        identity_row = connection.execute(
            """
            SELECT
                user_id,
                provider,
                subject,
                provider_email
            FROM user_identities
            WHERE user_id = ?
            """,
            (
                user.id,
            ),
        ).fetchone()

        assert identity_row is not None
        assert (
            identity_row["provider"]
            == "google"
        )
        assert (
            identity_row["subject"]
            == "google-subject-new"
        )
        assert (
            identity_row["provider_email"]
            == "google@example.com"
        )

    finally:
        connection.close()


def test_google_registration_requires_registration_state(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    service = GoogleAccountService()

    resolution = GoogleIdentityResolution(
        status=GoogleIdentityService.LINKED,
        subject="google-subject",
        email="google@example.com",
        display_name="Google User",
        user=None,
    )

    with pytest.raises(
        ValueError,
        match="not eligible for registration",
    ):
        service.register(
            resolution
        )


def test_google_registration_rolls_back_on_identity_conflict(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "existing-user",
                "existing@example.com",
                "Existing User",
                None,
                "user",
                None,
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
            ),
        )

        connection.execute(
            """
            INSERT INTO user_identities (
                id,
                user_id,
                provider,
                subject,
                provider_email,
                created_at,
                updated_at,
                last_authenticated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "existing-identity",
                "existing-user",
                "google",
                "conflicting-subject",
                "existing@example.com",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
            ),
        )

        connection.commit()

        users_before = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()["total"]

        candidates_before = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM candidates
            """
        ).fetchone()["total"]

    finally:
        connection.close()

    service = GoogleAccountService()

    with pytest.raises(
        sqlite3.IntegrityError
    ):
        service.register(
            _registration_resolution(
                subject="conflicting-subject",
                email="new-google@example.com",
            )
        )

    connection = _open_database(
        database_file
    )

    try:
        users_after = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()["total"]

        candidates_after = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM candidates
            """
        ).fetchone()["total"]

        attempted_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (
                "new-google@example.com",
            ),
        ).fetchone()

        assert users_after == users_before
        assert candidates_after == candidates_before
        assert attempted_user is None

    finally:
        connection.close()

def _insert_existing_user(
    database_file,
    *,
    user_id="existing-workpilot-user",
    email="existing@example.com",
):
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
                user_id,
                email,
                "Existing WorkPilot User",
                None,
                "user",
                "stored-password-hash",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return AppUser(
        id=user_id,
        email=email,
        display_name="Existing WorkPilot User",
        candidate_id=None,
        access_level="user",
    )


def _link_required_resolution(
    user,
):
    return GoogleIdentityResolution(
        status=(
            GoogleIdentityService
            .LINK_REQUIRED
        ),
        subject="google-existing-subject",
        email=user.email,
        display_name=user.display_name,
        user=user,
    )


def test_existing_account_can_be_explicitly_linked(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    user = _insert_existing_user(
        database_file
    )

    service = GoogleAccountService()

    result = service.link_existing_account(
        resolution=(
            _link_required_resolution(
                user
            )
        ),
        authenticated_user=user,
    )

    assert result == user

    connection = _open_database(
        database_file
    )

    try:
        identity = connection.execute(
            """
            SELECT
                user_id,
                provider,
                subject,
                provider_email
            FROM user_identities
            WHERE user_id = ?
            """,
            (
                user.id,
            ),
        ).fetchone()

        assert identity is not None
        assert (
            identity["provider"]
            == "google"
        )
        assert (
            identity["subject"]
            == "google-existing-subject"
        )
        assert (
            identity["provider_email"]
            == user.email
        )

        audit_event = connection.execute(
            """
            SELECT *
            FROM security_audit_events
            WHERE event_type = ?
            """,
            ("account.identity.linked",),
        ).fetchone()

        assert audit_event is not None
        assert (
            audit_event["authenticated_user_id"]
            == user.id
        )
        assert audit_event["active_user_id"] == user.id
        assert audit_event["target_id"] == user.id
        assert (
            audit_event["metadata_json"]
            == '{"provider": "google"}'
        )

    finally:
        connection.close()


def test_different_workpilot_account_cannot_be_linked(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    expected_user = _insert_existing_user(
        database_file,
        user_id="expected-user",
        email="expected@example.com",
    )

    other_user = AppUser(
        id="other-user",
        email="other@example.com",
        display_name="Other User",
        candidate_id=None,
        access_level="user",
    )

    service = GoogleAccountService()

    with pytest.raises(
        ValueError,
        match=(
            "does not match the Google identity"
        ),
    ):
        service.link_existing_account(
            resolution=(
                _link_required_resolution(
                    expected_user
                )
            ),
            authenticated_user=other_user,
        )

    connection = _open_database(
        database_file
    )

    try:
        total = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM user_identities
            """
        ).fetchone()["total"]

        assert total == 0

    finally:
        connection.close()


def test_linking_requires_link_required_state(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    user = _insert_existing_user(
        database_file
    )

    resolution = GoogleIdentityResolution(
        status=(
            GoogleIdentityService.LINKED
        ),
        subject="google-subject",
        email=user.email,
        display_name=user.display_name,
        user=user,
    )

    service = GoogleAccountService()

    with pytest.raises(
        ValueError,
        match=(
            "not eligible for account linking"
        ),
    ):
        service.link_existing_account(
            resolution=resolution,
            authenticated_user=user,
        )
