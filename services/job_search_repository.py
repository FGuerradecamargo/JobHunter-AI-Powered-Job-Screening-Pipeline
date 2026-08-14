from __future__ import annotations

from services.database import get_connection


class JobSearchRepository:
    def list_global_jobs(
        self,
        limit: int = 100,
        categories: list[str] | None = None,
    ):
        params = []

        category_filter = ""

        if categories:
            placeholders = ",".join(
                "%s"
                for _ in categories
            )

            category_filter = (
                f"WHERE category IN ({placeholders})"
            )

            params.extend(categories)

        params.append(limit)

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

            {category_filter}

            ORDER BY created_at DESC
            LIMIT %s
        """

        with get_connection() as connection:
            return connection.execute(
                query,
                params,
            ).fetchall()

    def list_user_jobs(
        self,
        user_id: str,
        limit: int = 100,
        categories: list[str] | None = None,
    ):
        params = [
            user_id,
        ]

        category_filter = ""

        if categories:
            placeholders = ",".join(
                "%s"
                for _ in categories
            )

            category_filter = (
                f"AND jobs.category IN ({placeholders})"
            )

            params.extend(categories)

        params.append(limit)

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

                {category_filter}

            ORDER BY jobs.created_at DESC
            LIMIT %s
        """

        with get_connection() as connection:
            return connection.execute(
                query,
                params,
            ).fetchall()
