from services.database import (
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
        user_id: str,
        keywords: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
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
                user_id=user_id,
                source_type=source_type,
            )

        return result
