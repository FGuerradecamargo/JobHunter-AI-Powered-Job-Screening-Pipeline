from __future__ import annotations

from services.database import get_connection


class JobSearchRepository:
    def list_global_jobs(
        self,
        categories: list[str],
        limit: int = 100,
    ):
        if not categories:
            return []

        placeholders = ",".join(
            "%s"
            for _ in categories
        )

        query = f"""
            SELECT
                id,
                title,
                company,
                location,
                url,
                category,
                sub_category,
                created_at
            FROM jobs
            WHERE category IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT %s
        """

        params = [
            *categories,
            limit,
        ]

        with get_connection() as connection:
            return connection.execute(
                query,
                params,
            ).fetchall()

    def list_user_jobs(
        self,
        user_id: str,
        categories: list[str],
        limit: int = 100,
    ):
        if not categories:
            return []

        placeholders = ",".join(
            "%s"
            for _ in categories
        )

        query = f"""
            SELECT DISTINCT
                jobs.id,
                jobs.title,
                jobs.company,
                jobs.location,
                jobs.url,
                jobs.category,
                jobs.sub_category,
                jobs.created_at
            FROM jobs

            INNER JOIN job_sources
                ON job_sources.job_id = jobs.id

            WHERE
                job_sources.user_id = %s
                AND jobs.category IN ({placeholders})

            ORDER BY jobs.created_at DESC
            LIMIT %s
        """

        params = [
            user_id,
            *categories,
            limit,
        ]

        with get_connection() as connection:
            return connection.execute(
                query,
                params,
            ).fetchall()
