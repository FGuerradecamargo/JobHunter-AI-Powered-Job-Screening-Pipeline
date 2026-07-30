from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from services.database import get_connection


class GmailMessageRepository:
    def register_if_new(
            self,
            user_id: str,
            gmail_message_id: str,
            gmail_thread_id: Optional[str] = None,
            received_at: Optional[str] = None,
            subject: Optional[str] = None,
            sender: Optional[str] = None,
            snippet: Optional[str] = None,
            raw_html: Optional[str] = None,
    ) -> bool:
        if not user_id:
            raise ValueError("User ID is required.")

        if not gmail_message_id:
            raise ValueError(
                "Gmail message ID is required."
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        content_fetched_at = (
            now if raw_html else None
        )

        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO gmail_messages (
                    user_id,
                    gmail_message_id,
                    gmail_thread_id,
                    received_at,
                    subject,
                    sender,
                    snippet,
                    raw_html,
                    content_fetched_at,
                    processed_at,
                    processing_status,
                    error_message,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    NULL, 'pending', NULL, ?
                )
                """,
                (
                    user_id,
                    gmail_message_id,
                    gmail_thread_id,
                    received_at,
                    subject,
                    sender,
                    snippet,
                    raw_html,
                    content_fetched_at,
                    now,
                ),
            )

        return cursor.rowcount > 0

    def list_pending(
            self,
            user_id: str,
            limit: int = 100,
    ) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    user_id,
                    gmail_message_id,
                    gmail_thread_id,
                    received_at,
                    subject,
                    sender,
                    snippet,
                    raw_html,
                    content_fetched_at,
                    processing_status
                FROM gmail_messages
                WHERE
                    user_id = ?
                    AND processing_status = 'pending'
                ORDER BY received_at ASC
                LIMIT ?
                """,
                (
                    user_id,
                    limit,
                ),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def exists(
        self,
        user_id: str,
        gmail_message_id: str,
    ) -> bool:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM gmail_messages
                WHERE
                    user_id = ?
                    AND gmail_message_id = ?
                """,
                (
                    user_id,
                    gmail_message_id,
                ),
            ).fetchone()

        return row is not None

    def mark_processed(
        self,
        user_id: str,
        gmail_message_id: str,
    ) -> None:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE gmail_messages
                SET
                    processing_status = 'processed',
                    processed_at = ?,
                    error_message = NULL
                WHERE
                    user_id = ?
                    AND gmail_message_id = ?
                """,
                (
                    now,
                    user_id,
                    gmail_message_id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(
                "Gmail message was not found."
            )

    def mark_failed(
        self,
        user_id: str,
        gmail_message_id: str,
        error_message: str,
    ) -> None:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE gmail_messages
                SET
                    processing_status = 'failed',
                    processed_at = ?,
                    error_message = ?
                WHERE
                    user_id = ?
                    AND gmail_message_id = ?
                """,
                (
                    now,
                    error_message,
                    user_id,
                    gmail_message_id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(
                "Gmail message was not found."
            )

    def count_by_status(
        self,
        user_id: str,
    ) -> dict[str, int]:
        counts = {
            "pending": 0,
            "processed": 0,
            "failed": 0,
        }

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    processing_status,
                    COUNT(*) AS total
                FROM gmail_messages
                WHERE user_id = ?
                GROUP BY processing_status
                """,
                (user_id,),
            ).fetchall()

        for row in rows:
            status = row["processing_status"]

            if status in counts:
                counts[status] = row["total"]

        return counts