from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from services.global_ingestion_plan import (
    build_daily_query_plan,
)
from services.job_import_service import (
    JobImportService,
)
from services.job_sources.adzuna_source import (
    AdzunaJobSource,
)
from services.job_sources.jooble_source import (
    JoobleJobSource,
)


@dataclass
class SourceIngestionResult:
    source_type: str
    queries_run: int = 0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed_queries: int = 0


@dataclass
class DailyIngestionResult:
    day_index: int
    jooble: SourceIngestionResult
    adzuna: SourceIngestionResult


class DailyIngestionService:

    def __init__(
        self,
        import_service: JobImportService | None = None,
    ) -> None:
        self.import_service = (
            import_service
            or JobImportService()
        )

    @staticmethod
    def current_day_index() -> int:
        now = datetime.now(
            timezone.utc
        )

        return now.toordinal()

    def _run_source(
        self,
        source,
        source_type: str,
        location: str,
        day_index: int,
        results_per_page: int,
    ) -> SourceIngestionResult:

        result = SourceIngestionResult(
            source_type=source_type
        )

        plan = build_daily_query_plan(
            day_index=day_index,
            source_type=source_type,
        )

        for item in plan:
            try:
                imported = (
                    self.import_service.import_jobs(
                        source=source,
                        source_type=source_type,
                        keywords=item["query"],
                        location=location,
                        results_per_page=results_per_page,
                    )
                )

                result.queries_run += 1
                result.fetched += imported[
                    "fetched"
                ]
                result.created += imported[
                    "created"
                ]
                result.updated += imported[
                    "updated"
                ]
                result.unchanged += imported[
                    "unchanged"
                ]

            except Exception as error:
                result.failed_queries += 1

                print(
                    "[INGESTION ERROR]",
                    source_type,
                    "|",
                    item["query"],
                    "|",
                    repr(error),
                )

        return result

    def run(
        self,
        day_index: int | None = None,
        jooble_results_per_query: int = 20,
        adzuna_results_per_query: int = 20,
    ) -> DailyIngestionResult:

        resolved_day_index = (
            day_index
            if day_index is not None
            else self.current_day_index()
        )

        jooble_result = self._run_source(
            source=JoobleJobSource(),
            source_type="jooble",
            location="Ireland",
            day_index=resolved_day_index,
            results_per_page=(
                jooble_results_per_query
            ),
        )

        adzuna_result = self._run_source(
            source=AdzunaJobSource(
                country="gb"
            ),
            source_type="adzuna",
            location="",
            day_index=resolved_day_index,
            results_per_page=(
                adzuna_results_per_query
            ),
        )

        return DailyIngestionResult(
            day_index=resolved_day_index,
            jooble=jooble_result,
            adzuna=adzuna_result,
        )
