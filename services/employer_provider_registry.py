from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from models.company import CompanyJobSource
from services.job_sources.provider import JobSourceProvider, ProviderConfig


def employer_run_name(source: CompanyJobSource) -> str:
    return f"{source.source_type}:{source.id}"


def _employer_plan(**_kwargs) -> list[dict]:
    return [{"query": ""}]


def build_employer_provider_configs(
    sources: Iterable[CompanyJobSource],
    factories: Mapping[str, Callable[[CompanyJobSource], JobSourceProvider]],
) -> tuple[ProviderConfig, ...]:
    """Translate trusted registry rows only; neither reads watchlists nor fetches jobs."""
    configs = {}
    for source in sources:
        if not source.enabled or source.source_type not in factories:
            continue
        name = employer_run_name(source)
        factory = factories[source.source_type]
        configs[name] = ProviderConfig(
            source_type=name,
            factory=lambda row=source, build=factory: build(row),
            query_plan=_employer_plan,
        )
    return tuple(configs.values())
