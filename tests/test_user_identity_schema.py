from __future__ import annotations

import sqlite3

import pytest

import services.database as database_module


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
        / "user-identities.db"
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

    # Must remain idempotent.
    database_module.initialize_sqlite_database()
    database_module.initialize_sqlite_database()

    return database_file


def _insert_user(
    connection,
    *,
    user_id,
    email,
):
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
            "Test User",
            None,
            "user",
            None,
            None,
            "2026-09-06T00:00:00+00:00",
            "2026-09-06T00:00:00+00:00",
        ),
    )


def test_user_identity_schema_is_created(
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
        columns = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    user_identities
                )
                """
            ).fetchall()
        }

        assert columns == {
            "id",
            "user_id",
            "provider",
            "subject",
            "provider_email",
            "created_at",
            "updated_at",
            "last_authenticated_at",
        }

        indexes = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA index_list(
                    user_identities
                )
                """
            ).fetchall()
        }

        assert (
            "idx_user_identities_user"
            in indexes
        )

    finally:
        connection.close()


def test_user_identity_uniqueness_constraints(
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
        _insert_user(
            connection,
            user_id="user-a",
            email="a@example.com",
        )

        _insert_user(
            connection,
            user_id="user-b",
            email="b@example.com",
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
                "identity-a",
                "user-a",
                "google",
                "google-subject-a",
                "a@example.com",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
            ),
        )

        # One Google subject cannot belong
        # to two WorkPilot users.
        with pytest.raises(
            sqlite3.IntegrityError
        ):
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
                    "identity-duplicate-subject",
                    "user-b",
                    "google",
                    "google-subject-a",
                    "b@example.com",
                    "2026-09-06T00:00:00+00:00",
                    "2026-09-06T00:00:00+00:00",
                    "2026-09-06T00:00:00+00:00",
                ),
            )

        # One WorkPilot user cannot have two
        # identities for the same provider.
        with pytest.raises(
            sqlite3.IntegrityError
        ):
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
                    "identity-duplicate-provider",
                    "user-a",
                    "google",
                    "different-google-subject",
                    "a@example.com",
                    "2026-09-06T00:00:00+00:00",
                    "2026-09-06T00:00:00+00:00",
                    "2026-09-06T00:00:00+00:00",
                ),
            )

    finally:
        connection.close()


def test_user_identity_requires_user_and_cascades(
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
        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO user_identities (
                    id,
                    user_id,
                    provider,
                    subject,
                    created_at,
                    updated_at,
                    last_authenticated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "orphan-identity",
                    "missing-user",
                    "google",
                    "orphan-subject",
                    "2026-09-06T00:00:00+00:00",
                    "2026-09-06T00:00:00+00:00",
                    "2026-09-06T00:00:00+00:00",
                ),
            )

        _insert_user(
            connection,
            user_id="cascade-user",
            email="cascade@example.com",
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
                "cascade-identity",
                "cascade-user",
                "google",
                "cascade-subject",
                "cascade@example.com",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
                "2026-09-06T00:00:00+00:00",
            ),
        )

        connection.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (
                "cascade-user",
            ),
        )

        remaining = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM user_identities
            WHERE user_id = ?
            """,
            (
                "cascade-user",
            ),
        ).fetchone()["total"]

        assert remaining == 0

    finally:
        connection.close()
