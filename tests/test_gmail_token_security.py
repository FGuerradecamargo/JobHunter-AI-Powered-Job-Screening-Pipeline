from __future__ import annotations

import sqlite3

import services.database as database_module


def test_existing_sqlite_gmail_table_gains_encrypted_access_token(
    monkeypatch,
    tmp_path,
):
    database_file = (
        tmp_path
        / "legacy-gmail.db"
    )

    # Simulate the pre-migration Gmail schema.
    connection = sqlite3.connect(
        database_file
    )

    connection.execute(
        """
        CREATE TABLE gmail_connections (
            user_id TEXT PRIMARY KEY,
            gmail_address TEXT NOT NULL UNIQUE,
            encrypted_refresh_token TEXT NOT NULL,
            access_token TEXT,
            token_expiry TEXT,
            scopes_json TEXT NOT NULL,
            last_history_id TEXT,
            last_sync_at TEXT,
            connection_status TEXT
                NOT NULL DEFAULT 'connected',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.commit()
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

    database_module.initialize_sqlite_database()

    # Running migrations again must be harmless.
    database_module.initialize_sqlite_database()

    connection = sqlite3.connect(
        database_file
    )

    try:
        columns = {
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    gmail_connections
                )
                """
            ).fetchall()
        }
    finally:
        connection.close()

    assert (
        "encrypted_access_token"
        in columns
    )

import json
from contextlib import contextmanager

import pytest
from cryptography.fernet import Fernet

from models.gmail_connection import GmailConnection
import services.gmail_connection_repository as gmail_repository_module
from services.gmail_connection_repository import (
    GmailConnectionRepository,
)
from services.token_encryption_service import (
    TokenEncryptionService,
)


def _create_gmail_repository_test_database(
    database_file,
):
    connection = sqlite3.connect(
        database_file
    )
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE gmail_connections (
            user_id TEXT PRIMARY KEY,
            gmail_address TEXT NOT NULL UNIQUE,
            encrypted_refresh_token TEXT NOT NULL,
            access_token TEXT,
            encrypted_access_token TEXT,
            token_expiry TEXT,
            scopes_json TEXT NOT NULL,
            last_history_id TEXT,
            last_sync_at TEXT,
            connection_status TEXT
                NOT NULL DEFAULT 'connected',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


def _patch_gmail_repository_connection(
    monkeypatch,
    database_file,
):
    @contextmanager
    def sqlite_connection():
        connection = sqlite3.connect(
            database_file
        )
        connection.row_factory = sqlite3.Row

        try:
            with connection:
                yield connection
        finally:
            connection.close()

    monkeypatch.setattr(
        gmail_repository_module,
        "get_connection",
        sqlite_connection,
    )


def _build_encryption_service():
    return TokenEncryptionService(
        encryption_key=(
            Fernet.generate_key().decode(
                "utf-8"
            )
        )
    )


def test_new_gmail_access_token_is_encrypted_at_rest(
    monkeypatch,
    tmp_path,
):
    database_file = (
        tmp_path
        / "encrypted-access-token.db"
    )

    _create_gmail_repository_test_database(
        database_file
    )

    _patch_gmail_repository_connection(
        monkeypatch,
        database_file,
    )

    encryption_service = (
        _build_encryption_service()
    )

    repository = GmailConnectionRepository(
        token_encryption_service=(
            encryption_service
        )
    )

    plain_access_token = (
        "synthetic-access-token-secret"
    )

    repository.save(
        GmailConnection(
            user_id="encrypted-user",
            gmail_address=(
                "encrypted-user@gmail.com"
            ),
            refresh_token=(
                "synthetic-refresh-token"
            ),
            access_token=plain_access_token,
            scopes=["gmail.readonly"],
        )
    )

    connection = sqlite3.connect(
        database_file
    )
    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            """
            SELECT
                access_token,
                encrypted_access_token
            FROM gmail_connections
            WHERE user_id = ?
            """,
            (
                "encrypted-user",
            ),
        ).fetchone()
    finally:
        connection.close()

    assert row is not None

    assert row["access_token"] is None

    assert (
        row["encrypted_access_token"]
        is not None
    )

    assert (
        row["encrypted_access_token"]
        != plain_access_token
    )

    assert encryption_service.decrypt(
        row["encrypted_access_token"]
    ) == plain_access_token

    loaded = repository.get_by_user_id(
        "encrypted-user"
    )

    assert loaded is not None

    assert (
        loaded.access_token
        == plain_access_token
    )


def test_legacy_plaintext_access_token_remains_readable(
    monkeypatch,
    tmp_path,
):
    database_file = (
        tmp_path
        / "legacy-access-token.db"
    )

    _create_gmail_repository_test_database(
        database_file
    )

    _patch_gmail_repository_connection(
        monkeypatch,
        database_file,
    )

    encryption_service = (
        _build_encryption_service()
    )

    repository = GmailConnectionRepository(
        token_encryption_service=(
            encryption_service
        )
    )

    encrypted_refresh_token = (
        encryption_service.encrypt(
            "synthetic-refresh-token"
        )
    )

    connection = sqlite3.connect(
        database_file
    )

    try:
        connection.execute(
            """
            INSERT INTO gmail_connections (
                user_id,
                gmail_address,
                encrypted_refresh_token,
                access_token,
                encrypted_access_token,
                token_expiry,
                scopes_json,
                last_history_id,
                last_sync_at,
                connection_status,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?
            )
            """,
            (
                "legacy-user",
                "legacy-user@gmail.com",
                encrypted_refresh_token,
                "legacy-plaintext-token",
                None,
                None,
                json.dumps(
                    ["gmail.readonly"]
                ),
                None,
                None,
                "connected",
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    loaded = repository.get_by_user_id(
        "legacy-user"
    )

    assert loaded is not None

    assert (
        loaded.access_token
        == "legacy-plaintext-token"
    )


def test_corrupt_encrypted_access_token_fails_closed(
    monkeypatch,
    tmp_path,
):
    database_file = (
        tmp_path
        / "corrupt-access-token.db"
    )

    _create_gmail_repository_test_database(
        database_file
    )

    _patch_gmail_repository_connection(
        monkeypatch,
        database_file,
    )

    encryption_service = (
        _build_encryption_service()
    )

    repository = GmailConnectionRepository(
        token_encryption_service=(
            encryption_service
        )
    )

    encrypted_refresh_token = (
        encryption_service.encrypt(
            "synthetic-refresh-token"
        )
    )

    connection = sqlite3.connect(
        database_file
    )

    try:
        connection.execute(
            """
            INSERT INTO gmail_connections (
                user_id,
                gmail_address,
                encrypted_refresh_token,
                access_token,
                encrypted_access_token,
                token_expiry,
                scopes_json,
                last_history_id,
                last_sync_at,
                connection_status,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?
            )
            """,
            (
                "corrupt-user",
                "corrupt-user@gmail.com",
                encrypted_refresh_token,
                "legacy-token-must-not-win",
                "not-valid-fernet-ciphertext",
                None,
                json.dumps(
                    ["gmail.readonly"]
                ),
                None,
                None,
                "connected",
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        ValueError,
        match=(
            "encrypted token is invalid"
        ),
    ):
        repository.get_by_user_id(
            "corrupt-user"
        )
