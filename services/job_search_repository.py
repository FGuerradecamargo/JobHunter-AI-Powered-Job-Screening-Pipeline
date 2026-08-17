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

    def list_jobs_to_analyze_for_candidate(
        self,
        candidate_id: str,
        analysis_version: str,
        candidate_signature: str,
        limit: int = 100,
    ):
        """
        Returns global jobs that still need analysis for this candidate.

        A job is eligible when:
        - the candidate has never received an analysis for it; or
        - the existing system analysis is stale because the analysis
          version or candidate profile signature changed.

        User decisions such as applied or user_rejected are preserved.
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
                candidate_job_analyses.job_id IS NULL

                OR (
                    candidate_job_analyses.status IN (
                        'in_review',
                        'system_rejected'
                    )

                    AND (
                        candidate_job_analyses.recommendation IS NULL

                        OR COALESCE(
                            candidate_job_analyses.analysis_version,
                            ''
                        ) != %s

                        OR COALESCE(
                            candidate_job_analyses.candidate_signature,
                            ''
                        ) != %s
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
                    analysis_version,
                    candidate_signature,
                    limit,
                ),
            ).fetchall()

