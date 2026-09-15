from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from models.job import Job
from services.global_ingestion_plan import build_daily_query_plan


@runtime_checkable
class JobSourceProvider(Protocol):
    source_type: str

    def search(
        self, keywords: str, location: str, page: int = 1,
        results_per_page: int = 20,
    ) -> list[Job]: ...


@dataclass(frozen=True)
class ProviderConfig:
    source_type: str
    factory: Callable[[], JobSourceProvider]
    location: str = ""
    results_per_query: int = 20
    enabled: bool = True
    query_plan: Callable[..., list[dict]] = build_daily_query_plan


def default_providers(
    jooble_results: int = 20, adzuna_results: int = 20,
) -> tuple[ProviderConfig, ...]:
    from services.job_sources.adzuna_source import AdzunaJobSource
    from services.job_sources.jooble_source import JoobleJobSource

    return (
        ProviderConfig("jooble", JoobleJobSource, "Ireland", jooble_results),
        ProviderConfig("adzuna", lambda: AdzunaJobSource(country="gb"), "", adzuna_results),
    )
