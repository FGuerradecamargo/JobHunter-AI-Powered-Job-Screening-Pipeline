from services.job_observation import is_personal_source
from services.job_observation_repository import JobObservationRepository
from services.job_source_repository import JobSourceRepository
from services.job_sources.base_job_source import JobSource


class JobImportService:
    def __init__(self, source_repository: JobSourceRepository | None = None) -> None:
        self.source_repository = source_repository or JobSourceRepository()
        self.observations = JobObservationRepository(self.source_repository)

    def import_jobs(
        self, source: JobSource, source_type: str, keywords: str, location: str,
        user_id: str | None = None, page: int = 1, results_per_page: int = 20,
        discovery_category: str | None = None, discovery_sub_category: str | None = None,
        discovery_query: str | None = None,
    ) -> dict[str, int]:
        source_type = str(source_type or "").strip().lower()
        if user_id is not None and not str(user_id).strip():
            raise ValueError("Personal sources require a user.")
        if is_personal_source(source_type) and user_id is None:
            raise ValueError("Personal sources require a user.")
        jobs = source.search(keywords=keywords, location=location, page=page,
                             results_per_page=results_per_page)
        result = dict(fetched=len(jobs), created=0, updated=0, unchanged=0)
        for job in jobs:
            job_id, status = self.observations.record(
                job, source_type, user_id=user_id, trusted_public=user_id is None,
            )
            result[status] += 1
            if user_id is None and discovery_category and discovery_sub_category and discovery_query:
                self.source_repository.add_discovery_signal(
                    job_id=job_id, source_type=source_type, category=discovery_category,
                    sub_category=discovery_sub_category, search_query=discovery_query,
                )
        return result
