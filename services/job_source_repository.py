from __future__ import annotations

from datetime import datetime, timezone

from services.database import get_connection


class JobSourceRepository:
    def add_source(
        self,
        job_id: str,
        user_id: str,
        source_type: str,
    ) -> None:
        discovered_at = (
            datetime.now(timezone.utc).isoformat()
        )

        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO job_sources (
                    job_id,
                    user_id,
                    source_type,
                    discovered_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    job_id,
                    user_id,
                    source_type,
                    discovered_at,
                ),
            )

    def list_by_user(
        self,
        user_id: str,
    ) -> list[str]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT job_id
                FROM job_sources
                WHERE user_id = ?
                ORDER BY discovered_at DESC
                """,
                (user_id,),
            ).fetchall()

        return [
            row["job_id"]
            for row in rows
        ]

    def list_sources_for_job(
        self,
        job_id: str,
    ):
        with get_connection() as connection:
            return connection.execute(
                """
                SELECT
                    user_id,
                    source_type,
                    discovered_at
                FROM job_sources
                WHERE job_id = ?
                ORDER BY discovered_at ASC
                """,
                (job_id,),
            ).fetchall()
