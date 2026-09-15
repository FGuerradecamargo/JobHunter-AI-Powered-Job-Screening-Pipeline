from dataclasses import replace

from services.job_observation import normalize_observation, is_personal_source
from services.database import (
    get_connection,
    upsert_raw_job,
)
from services.job_source_repository import (
    JobSourceRepository,
)
from services.job_sources.base_job_source import (
    JobSource,
)


class JobImportService:

    def __init__(
        self,
        source_repository: (
            JobSourceRepository | None
        ) = None,
    ) -> None:
        self.source_repository = (
            source_repository
            or JobSourceRepository()
        )

    def import_jobs(
        self,
        source: JobSource,
        source_type: str,
        keywords: str,
        location: str,
        user_id: str | None = None,
        page: int = 1,
        results_per_page: int = 20,
        discovery_category: str | None = None,
        discovery_sub_category: str | None = None,
        discovery_query: str | None = None,
    ) -> dict[str, int]:
        source_type = str(source_type or "").strip().lower()
        if user_id is not None and not str(user_id).strip():
            raise ValueError("Personal sources require a user.")
        if is_personal_source(source_type) and user_id is None:
            raise ValueError("Personal sources require a user.")
        jobs = source.search(
            keywords=keywords,
            location=location,
            page=page,
            results_per_page=(
                results_per_page
            ),
        )

        result = {
            "fetched": len(jobs),
            "created": 0,
            "updated": 0,
            "unchanged": 0,
        }

        for job in jobs:
            job = normalize_observation(job, source_type).job
            if user_id is None:
                job = replace(job, id=self._canonical_global_id(job))
            status = upsert_raw_job(
                job
            )

            if status in result:
                result[status] += 1

            self.source_repository.add_source(
                job_id=job.id,
                source_type=source_type,
                user_id=user_id,
            )

            # Search-taxonomy evidence is global.
            # Never persist candidate/user-specific discovery
            # metadata into the shared discovery-signal layer.
            if (
                user_id is None
                and discovery_category
                and discovery_sub_category
                and discovery_query
            ):
                self.source_repository.add_discovery_signal(
                    job_id=job.id,
                    source_type=source_type,
                    category=discovery_category,
                    sub_category=discovery_sub_category,
                    search_query=discovery_query,
                )

            if user_id is None:
                with get_connection() as connection:
                    connection.execute(
                        """
                        UPDATE jobs
                        SET archived_at = NULL
                        WHERE
                            id = ?
                            AND archived_at IS NOT NULL
                        """,
                        (job.id,),
                    )

        return result

    @staticmethod
    def _canonical_global_id(job):
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT id FROM jobs WHERE id = ?", (job.id,),
            ).fetchone()
            if existing is not None:
                personal = connection.execute(
                    "SELECT 1 FROM job_sources WHERE job_id = ? AND user_id IS NOT NULL",
                    (job.id,),
                ).fetchone()
                if personal:
                    raise ValueError("Global import cannot promote a personal record.")
                return job.id
            if not job.url or not job.company or not job.location:
                return job.id
            matches = connection.execute(
                """
                SELECT jobs.id FROM jobs
                WHERE jobs.url = ?
                    AND LOWER(TRIM(jobs.title)) = LOWER(TRIM(?))
                    AND LOWER(TRIM(jobs.company)) = LOWER(TRIM(?))
                    AND LOWER(TRIM(jobs.location)) = LOWER(TRIM(?))
                    AND EXISTS (
                        SELECT 1 FROM job_sources s
                        WHERE s.job_id = jobs.id AND s.user_id IS NULL
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM job_sources s
                        WHERE s.job_id = jobs.id AND s.user_id IS NOT NULL
                    )
                LIMIT 2
                """,
                (job.url, job.title, job.company, job.location),
            ).fetchall()
        return matches[0]["id"] if len(matches) == 1 else job.id
