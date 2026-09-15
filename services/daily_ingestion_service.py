from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic

from services.job_import_service import JobImportService
from services.job_sources.provider import ProviderConfig, default_providers


@dataclass
class SourceIngestionResult:
    source_type: str
    queries_run: int = 0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed_queries: int = 0
    status: str = "success"
    error_code: str | None = None
    duration_seconds: float = 0.0


@dataclass
class DailyIngestionResult:
    day_index: int
    providers: dict[str, SourceIngestionResult] = field(default_factory=dict)

    # Compatibility for callers reading the original two provider attributes.
    @property
    def jooble(self) -> SourceIngestionResult:
        return self.providers["jooble"]

    @property
    def adzuna(self) -> SourceIngestionResult:
        return self.providers["adzuna"]

    @property
    def totals(self) -> dict[str, int]:
        return {
            name: sum(getattr(result, name) for result in self.providers.values())
            for name in (
                "queries_run", "fetched", "created", "updated", "unchanged", "failed_queries",
            )
        }


class DailyIngestionService:
    def __init__(
        self, import_service: JobImportService | None = None,
        providers: tuple[ProviderConfig, ...] | None = None,
    ) -> None:
        self.import_service = import_service or JobImportService()
        self.providers = providers

    @staticmethod
    def current_day_index() -> int:
        return datetime.now(timezone.utc).toordinal()

    def _run_provider(self, config: ProviderConfig, day_index: int) -> SourceIngestionResult:
        result = SourceIngestionResult(config.source_type)
        if not config.enabled:
            result.status = "disabled"
            return result
        started = monotonic()
        try:
            source = config.factory()
            if source.source_type != config.source_type:
                raise ValueError("Provider type mismatch.")
            plan = config.query_plan(day_index=day_index, source_type=config.source_type)
            for item in plan:
                result.queries_run += 1
                try:
                    imported = self.import_service.import_jobs(
                        source=source,
                        source_type=config.source_type,
                        keywords=item["query"],
                        location=config.location,
                        results_per_page=config.results_per_query,
                        discovery_category=item.get("category"),
                        discovery_sub_category=item.get("sub_category"),
                        discovery_query=item["query"],
                    )
                    for name in ("fetched", "created", "updated", "unchanged"):
                        setattr(result, name, getattr(result, name) + imported[name])
                except Exception:
                    result.failed_queries += 1
            if result.failed_queries:
                result.status = (
                    "failed" if result.failed_queries == result.queries_run else "partial"
                )
                result.error_code = "query_failed"
        except Exception:
            result.status = "failed"
            result.error_code = "provider_setup_failed"
        finally:
            result.duration_seconds = round(monotonic() - started, 4)
        return result

    def run(
        self, day_index: int | None = None,
        jooble_results_per_query: int = 20,
        adzuna_results_per_query: int = 20,
    ) -> DailyIngestionResult:
        day = day_index if day_index is not None else self.current_day_index()
        configs = self.providers if self.providers is not None else default_providers(
            jooble_results_per_query, adzuna_results_per_query,
        )
        names = [config.source_type for config in configs]
        if len(names) != len(set(names)) or any(not name.strip() for name in names):
            raise ValueError("Provider source types must be non-empty and unique.")
        return DailyIngestionResult(
            day_index=day,
            providers={config.source_type: self._run_provider(config, day) for config in configs},
        )
