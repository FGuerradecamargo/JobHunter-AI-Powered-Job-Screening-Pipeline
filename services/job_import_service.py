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
                            id = %s
                            AND archived_at IS NOT NULL
                        """,
                        (job.id,),
                    )

        return result
