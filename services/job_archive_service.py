from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.database import get_connection


class JobArchiveService:

    def archive_stale_global_jobs(
        self,
        stale_after_days: int = 30,
    ) -> int:
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=stale_after_days)
        ).isoformat()

        archived_at = (
            datetime.now(timezone.utc)
            .isoformat()
        )

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET archived_at = %s
                WHERE
                    archived_at IS NULL
                    AND id IN (
                        SELECT js.job_id
                        FROM job_sources js
                        GROUP BY js.job_id
                        HAVING
                            BOOL_AND(
                                js.user_id IS NULL
                            )
                            AND MAX(
                                js.last_seen_at
                            ) < %s
                    )
                """,
                (
                    archived_at,
                    cutoff,
                ),
            )

        return cursor.rowcount

    def reactivate_seen_global_jobs(
        self,
    ) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET archived_at = NULL
                WHERE
                    archived_at IS NOT NULL
                    AND id IN (
                        SELECT DISTINCT job_id
                        FROM job_sources
                        WHERE
                            user_id IS NULL
                            AND last_seen_at IS NOT NULL
                            AND last_seen_at >= archived_at
                    )
                """
            )

        return cursor.rowcount
