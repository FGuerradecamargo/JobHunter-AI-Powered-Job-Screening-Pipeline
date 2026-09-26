from __future__ import annotations

from datetime import datetime, timezone
from contextlib import nullcontext

from services.database import get_connection
from services.job_observation import is_personal_source


class JobSourceRepository:
    def add_source(
        self,
        job_id: str,
        source_type: str,
        user_id: str | None = None,
        *,
        connection=None,
    ) -> None:
        source_type = str(source_type or "").strip().lower()
        if not source_type or (user_id is not None and not str(user_id).strip()):
            raise ValueError("Source scope is invalid.")
        if is_personal_source(source_type) and user_id is None:
            raise ValueError("Personal sources require a user.")
        seen_at = (
            datetime.now(timezone.utc).isoformat()
        )

        with (nullcontext(connection) if connection is not None else get_connection()) as connection:
            if user_id is None:
                connection.execute(
                    """
                    INSERT INTO job_sources (
                        job_id,
                        user_id,
                        source_type,
                        discovered_at,
                        last_seen_at
                    )
                    VALUES (
                        ?,
                        NULL,
                        ?,
                        ?,
                        ?
                    )
                    ON CONFLICT (
                        job_id,
                        source_type
                    )
                    WHERE user_id IS NULL
                    DO UPDATE SET
                        last_seen_at = EXCLUDED.last_seen_at
                    """,
                    (
                        job_id,
                        source_type,
                        seen_at,
                        seen_at,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO job_sources (
                        job_id,
                        user_id,
                        source_type,
                        discovered_at,
                        last_seen_at
                    )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    ON CONFLICT (
                        job_id,
                        user_id,
                        source_type
                    )
                    WHERE user_id IS NOT NULL
                    DO UPDATE SET
                        last_seen_at = EXCLUDED.last_seen_at
                    """,
                    (
                        job_id,
                        user_id,
                        source_type,
                        seen_at,
                        seen_at,
                    ),
                )

    def add_discovery_signal(
        self,
        job_id: str,
        source_type: str,
        category: str,
        sub_category: str,
        search_query: str,
    ) -> None:
        """
        Persist global evidence describing how a job
        was discovered.

        Rediscovering the same signal updates only
        last_seen_at. A job may keep multiple signals
        from different searches or taxonomies.
        """
        seen_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        normalized_job_id = str(
            job_id or ""
        ).strip()

        normalized_source_type = str(
            source_type or ""
        ).strip()

        normalized_category = str(
            category or ""
        ).strip()

        normalized_sub_category = str(
            sub_category or ""
        ).strip()

        normalized_search_query = str(
            search_query or ""
        ).strip()

        if not all(
            (
                normalized_job_id,
                normalized_source_type,
                normalized_category,
                normalized_sub_category,
                normalized_search_query,
            )
        ):
            raise ValueError(
                "Discovery signal fields must be non-empty."
            )

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO job_discovery_signals (
                    job_id,
                    source_type,
                    category,
                    sub_category,
                    search_query,
                    first_seen_at,
                    last_seen_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )

                ON CONFLICT (
                    job_id,
                    source_type,
                    category,
                    sub_category,
                    search_query
                )
                DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at
                """,
                (
                    normalized_job_id,
                    normalized_source_type,
                    normalized_category,
                    normalized_sub_category,
                    normalized_search_query,
                    seen_at,
                    seen_at,
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
        user_id: str | None = None,
    ):
        with get_connection() as connection:
            return connection.execute(
                """
                SELECT
                    user_id,
                    source_type,
                    discovered_at,
                    last_seen_at
                FROM job_sources
                WHERE job_id = ?
                    AND (user_id IS NULL OR user_id = ?)
                ORDER BY discovered_at ASC
                """,
                (job_id, user_id),
            ).fetchall()
