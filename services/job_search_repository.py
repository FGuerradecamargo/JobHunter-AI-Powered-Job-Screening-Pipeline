from __future__ import annotations

from services.database import get_connection
from services.job_family_affinity import (
    score_job_family_affinity,
)


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
        target_families: list[str] | None = None,
        bridge_families: list[str] | None = None,
        competitive_families: list[str] | None = None,
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

        Family affinity changes discovery order only.
        It never removes an otherwise eligible job.

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
                jobs.created_at,

                job_discovery_signals.category
                    AS discovery_category,

                job_discovery_signals.sub_category
                    AS discovery_sub_category,

                job_discovery_signals.search_query
                    AS discovery_query

            FROM jobs

            LEFT JOIN candidate_job_analyses
                ON candidate_job_analyses.job_id = jobs.id
                AND candidate_job_analyses.candidate_id = %s

            LEFT JOIN job_discovery_signals
                ON job_discovery_signals.job_id = jobs.id

            WHERE
                jobs.archived_at IS NULL

                AND (
                    candidate_job_analyses.job_id IS NULL

                    OR (
                        candidate_job_analyses.analysis_state = 'pending'
                        AND candidate_job_analyses.opportunity_state = 'none'
                    )
                )

            ORDER BY
                jobs.created_at DESC,
                jobs.id
        """

        with get_connection() as connection:
            rows = connection.execute(
                query,
                (
                    candidate_id,
                ),
            ).fetchall()

        jobs_by_id: dict[str, dict] = {}

        for row in rows:
            job_id = str(
                row["id"]
            )

            if job_id not in jobs_by_id:
                jobs_by_id[job_id] = {
                    "id": row["id"],
                    "title": row["title"],
                    "company": row["company"],
                    "location": row["location"],
                    "url": row["url"],
                    "category": row["category"],
                    "sub_category": row["sub_category"],
                    "created_at": row["created_at"],
                    "_discovery_evidence": [],
                }

            evidence = jobs_by_id[
                job_id
            ]["_discovery_evidence"]

            for value in (
                row["discovery_category"],
                row["discovery_sub_category"],
                row["discovery_query"],
            ):
                normalized_value = str(
                    value or ""
                ).strip()

                if (
                    normalized_value
                    and normalized_value
                    not in evidence
                ):
                    evidence.append(
                        normalized_value
                    )

        ranked_jobs = []

        for job in jobs_by_id.values():
            evidence = [
                job["title"],
                job["category"],
                job["sub_category"],
                *job["_discovery_evidence"],
            ]

            affinity = score_job_family_affinity(
                target_families=(
                    target_families or []
                ),
                bridge_families=(
                    bridge_families or []
                ),
                competitive_families=(
                    competitive_families or []
                ),
                evidence=evidence,
            )

            ranked_jobs.append(
                (
                    affinity.score,
                    str(
                        job["created_at"]
                        or ""
                    ),
                    str(
                        job["id"]
                    ),
                    job,
                )
            )

        ranked_jobs.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
            reverse=True,
        )

        result = []

        for (
            _score,
            _created_at,
            _job_id,
            job,
        ) in ranked_jobs[:limit]:

            clean_job = {
                key: value
                for key, value
                in job.items()
                if not key.startswith("_")
            }

            result.append(
                clean_job
            )

        return result


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

