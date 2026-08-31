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
                f"AND category IN ({placeholders})"
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

            WHERE archived_at IS NULL

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
                AND jobs.archived_at IS NULL

                {category_filter}

            ORDER BY jobs.created_at DESC
            LIMIT %s
        """

        with get_connection() as connection:
            return connection.execute(
                query,
                params,
            ).fetchall()

    def list_jobs_to_analyze_for_candidate(
        self,
        candidate_id: str,
        analysis_version: str,
        candidate_signature: str,
        limit: int = 100,
    ):
        """
        Return jobs eligible for initial candidate discovery.

        Sprint 8.5:
        Discovery contains only:
        - jobs never linked to this candidate; or
        - relationships whose initial analysis is pending.

        Previously analyzed jobs never return to discovery
        because a model version, candidate signature or job
        signature changed. Those belong to reanalysis.

        analysis_version and candidate_signature remain as
        temporary compatibility parameters.
        """

        query = """
            SELECT
                jobs.id,
                jobs.title,
                jobs.company,
                jobs.location,
                jobs.url,
                jobs.category,
                jobs.sub_category,
                jobs.created_at

            FROM jobs

            LEFT JOIN candidate_job_analyses
                ON candidate_job_analyses.job_id = jobs.id
                AND candidate_job_analyses.candidate_id = %s

            WHERE
                jobs.archived_at IS NULL

                AND (
                    candidate_job_analyses.job_id IS NULL

                    OR (
                        candidate_job_analyses.analysis_state = 'pending'
                        AND candidate_job_analyses.opportunity_state = 'none'
                    )
                )

            ORDER BY jobs.created_at DESC

            LIMIT %s
        """

        with get_connection() as connection:
            return connection.execute(
                query,
                (
                    candidate_id,
                    limit,
                ),
            ).fetchall()


    def count_jobs_to_analyze_for_candidate(
        self,
        candidate_id: str,
        analysis_version: str,
        candidate_signature: str,
    ) -> int:
        """
        Count jobs eligible for initial discovery only.

        Stale/version/signature changes are intentionally
        excluded and will be handled by reanalysis.
        """

        query = """
            SELECT COUNT(*) AS total

            FROM jobs

            LEFT JOIN candidate_job_analyses
                ON candidate_job_analyses.job_id = jobs.id
                AND candidate_job_analyses.candidate_id = %s

            WHERE
                jobs.archived_at IS NULL

                AND (
                    candidate_job_analyses.job_id IS NULL

                    OR (
                        candidate_job_analyses.analysis_state = 'pending'
                        AND candidate_job_analyses.opportunity_state = 'none'
                    )
                )
        """

        with get_connection() as connection:
            row = connection.execute(
                query,
                (
                    candidate_id,
                ),
            ).fetchone()

        if not row:
            return 0

        return int(
            row["total"]
        )

