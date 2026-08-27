from __future__ import annotations

from services.global_job_search_catalog import (
    iter_global_search_queries,
)


SOURCE_QUERY_LIMITS = {
    "jooble": 20,
    "adzuna": 10,
}


def build_daily_query_plan(
    day_index: int,
    source_type: str,
) -> list[dict]:
    limit = SOURCE_QUERY_LIMITS[
        source_type
    ]

    all_queries = list(
        iter_global_search_queries()
    )

    if not all_queries:
        return []

    start = (
        day_index * limit
    ) % len(all_queries)

    plan = []

    for offset in range(limit):
        index = (
            start + offset
        ) % len(all_queries)

        plan.append(
            all_queries[index]
        )

    return plan
