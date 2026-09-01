from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from models.gmail_connection import GmailConnection
from services.database import get_connection
from services.token_encryption_service import (
    TokenEncryptionService,
)


class GmailConnectionRepository:
    def __init__(
        self,
        token_encryption_service: (
            TokenEncryptionService | None
        ) = None,
    ) -> None:
        self._token_encryption_service = (
            token_encryption_service
            or TokenEncryptionService()
        )

    def save(
        self,
        gmail_connection: GmailConnection,
    ) -> None:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        encrypted_refresh_token = (
            self._token_encryption_service.encrypt(
                gmail_connection.refresh_token,
            )
        )

        encrypted_access_token = None

        if gmail_connection.access_token:
            encrypted_access_token = (
                self._token_encryption_service.encrypt(
                    gmail_connection.access_token,
                )
            )

        with get_connection() as connection:
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
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )

                ON CONFLICT(user_id)
                DO UPDATE SET
                    gmail_address =
                        excluded.gmail_address,

                    encrypted_refresh_token =
                        excluded.encrypted_refresh_token,

                    access_token = NULL,

                    encrypted_access_token =
                        excluded.encrypted_access_token,

                    token_expiry =
                        excluded.token_expiry,

                    scopes_json =
                        excluded.scopes_json,

                    last_history_id =
                        excluded.last_history_id,

                    last_sync_at =
                        excluded.last_sync_at,

                    connection_status =
                        excluded.connection_status,

                    updated_at =
                        excluded.updated_at
                """,
                (
                    gmail_connection.user_id,
                    gmail_connection.gmail_address
                    .strip()
                    .lower(),
                    encrypted_refresh_token,
                    None,
                    encrypted_access_token,
                    gmail_connection.token_expiry,
                    json.dumps(
                        gmail_connection.scopes,
                        ensure_ascii=False,
                    ),
                    gmail_connection.last_history_id,
                    gmail_connection.last_sync_at,
                    gmail_connection.connection_status,
                    now,
                    now,
                ),
            )

    def get_by_user_id(
        self,
        user_id: str,
    ) -> Optional[GmailConnection]:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    gmail_address,
                    encrypted_refresh_token,
                    access_token,
                    encrypted_access_token,
                    token_expiry,
                    scopes_json,
                    last_history_id,
                    last_sync_at,
                    connection_status
                FROM gmail_connections
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        if (
            row["connection_status"] != "connected"
            or not row["encrypted_refresh_token"]
        ):
            return None

        access_token = None

        if row["encrypted_access_token"]:
            access_token = (
                self._token_encryption_service.decrypt(
                    row["encrypted_access_token"]
                )
            )
        elif row["access_token"]:
            access_token = row["access_token"]

        return GmailConnection(
            user_id=row["user_id"],
            gmail_address=row[
                "gmail_address"
            ],
            refresh_token=(
                self._token_encryption_service.decrypt(
                    row[
                        "encrypted_refresh_token"
                    ]
                )
            ),
            scopes=json.loads(
                row["scopes_json"]
            ),
            access_token=access_token,
            token_expiry=row[
                "token_expiry"
            ],
            last_history_id=row[
                "last_history_id"
            ],
            last_sync_at=row[
                "last_sync_at"
            ],
            connection_status=row[
                "connection_status"
            ],
        )

    def list_connected_user_ids(
        self,
    ) -> list[str]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT user_id
                FROM gmail_connections
                WHERE
                    connection_status = 'connected'
                    AND encrypted_refresh_token != ''
                ORDER BY user_id
                """
            ).fetchall()

        return [
            row["user_id"]
            for row in rows
        ]

    def update_sync_state(
        self,
        user_id: str,
        last_history_id: Optional[str],
        last_sync_at: Optional[str] = None,
    ) -> None:
        resolved_sync_at = (
            last_sync_at
            or datetime.now(
                timezone.utc
            ).isoformat()
        )

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE gmail_connections
                SET
                    last_history_id = ?,
                    last_sync_at = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    last_history_id,
                    resolved_sync_at,
                    resolved_sync_at,
                    user_id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(
                "Gmail connection not found for "
                f"user: {user_id}"
            )

    def disconnect(
        self,
        user_id: str,
    ) -> None:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE gmail_connections
                SET
                    connection_status = 'disconnected',
                    access_token = NULL,
                    encrypted_access_token = NULL,
                    encrypted_refresh_token = '',
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    now,
                    user_id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(
                "Gmail connection not found for "
                f"user: {user_id}"
            )
