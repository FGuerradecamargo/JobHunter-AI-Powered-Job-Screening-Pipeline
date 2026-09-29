from __future__ import annotations

from uuid import uuid4

from services.database import get_connection


class MembershipUsageRepository:

    def count(
        self,
        *,
        user_id: str,
        capability: str,
        window_start: str,
        window_end: str,
    ) -> int:

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    COALESCE(
                        SUM(quantity),
                        0
                    ) AS total
                FROM membership_usage_events
                WHERE user_id = ?
                  AND capability = ?
                  AND occurred_at >= ?
                  AND occurred_at < ?
                """,
                (
                    user_id,
                    capability,
                    window_start,
                    window_end,
                ),
            ).fetchone()

        return int(
            row["total"] or 0
        )

    def consume_limited(
        self,
        *,
        user_id: str,
        capability: str,
        amount: int,
        limit: int,
        window_start: str,
        window_end: str,
        idempotency_key: str,
        occurred_at: str,
    ) -> dict:

        with get_connection() as connection:

            cursor = connection.execute(
                """
                UPDATE users
                SET id = id
                WHERE id = ?
                """,
                (user_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "User was not found."
                )

            existing = connection.execute(
                """
                SELECT id
                FROM membership_usage_events
                WHERE user_id = ?
                  AND capability = ?
                  AND idempotency_key = ?
                """,
                (
                    user_id,
                    capability,
                    idempotency_key,
                ),
            ).fetchone()

            used = int(
                connection.execute(
                    """
                    SELECT
                        COALESCE(
                            SUM(quantity),
                            0
                        ) AS total
                    FROM membership_usage_events
                    WHERE user_id = ?
                      AND capability = ?
                      AND occurred_at >= ?
                      AND occurred_at < ?
                    """,
                    (
                        user_id,
                        capability,
                        window_start,
                        window_end,
                    ),
                ).fetchone()["total"]
                or 0
            )

            if existing is not None:
                return {
                    "status": "already_consumed",
                    "event_id": existing["id"],
                    "used": used,
                }

            if used + amount > limit:
                return {
                    "status": "limit_reached",
                    "event_id": "",
                    "used": used,
                }

            event_id = (
                "membership_usage_"
                + uuid4().hex
            )

            connection.execute(
                """
                INSERT INTO membership_usage_events (
                    id,
                    user_id,
                    capability,
                    quantity,
                    idempotency_key,
                    window_start,
                    window_end,
                    occurred_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    user_id,
                    capability,
                    amount,
                    idempotency_key,
                    window_start,
                    window_end,
                    occurred_at,
                ),
            )

            return {
                "status": "consumed",
                "event_id": event_id,
                "used": used + amount,
            }
