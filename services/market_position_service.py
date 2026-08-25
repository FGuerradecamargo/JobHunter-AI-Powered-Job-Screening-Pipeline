import json
import re
from collections import Counter
from typing import Any

from services.database import get_connection


COMPETITIVE_RECOMMENDATIONS = {
    "best_match",
    "potential",
    "good_opportunity",
}

NEAR_MATCH_MIN_FIT = 50


def _normalize(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[.;:,]+$", "", value)
    return value


def _display_label(value: str) -> str:
    return str(value or "").strip()


def _top_signals(
    values: list[str],
    limit: int = 5,
) -> list[dict[str, Any]]:
    labels: dict[str, str] = {}
    counter: Counter[str] = Counter()

    for value in values:
        normalized = _normalize(value)

        if not normalized:
            continue

        counter[normalized] += 1

        if normalized not in labels:
            labels[normalized] = _display_label(value)

    return [
        {
            "label": labels[key],
            "count": count,
        }
        for key, count in counter.most_common(limit)
    ]


def _is_competitive(item: dict[str, Any]) -> bool:
    return (
        item.get("recommendation")
        in COMPETITIVE_RECOMMENDATIONS
    )


def _is_near_market(item: dict[str, Any]) -> bool:
    if _is_competitive(item):
        return True

    fit = item.get("current_fit")

    return (
        isinstance(fit, int)
        and fit >= NEAR_MATCH_MIN_FIT
    )


def _aggregate(
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    recommendation_counter: Counter[str] = Counter()

    competitive_roles = []
    competitive_strengths = []

    near_market_blockers = []
    near_market_raise_fit = []

    fit_scores = []

    competitive_jobs = 0
    near_market_jobs = 0

    for item in signals:
        recommendation = str(
            item.get(
                "recommendation",
                "",
            )
        ).strip()

        if recommendation:
            recommendation_counter[
                recommendation
            ] += 1

        fit = item.get("current_fit")

        if isinstance(fit, int):
            fit_scores.append(fit)

        market_signal = (
            item.get("market_signal")
            or {}
        )

        if _is_competitive(item):
            competitive_jobs += 1

            role_family = market_signal.get(
                "role_family",
                "",
            )

            if role_family:
                competitive_roles.append(
                    role_family
                )

            competitive_strengths.extend(
                market_signal.get(
                    "market_strengths",
                    [],
                )
                or []
            )

        if _is_near_market(item):
            near_market_jobs += 1

            near_market_blockers.extend(
                market_signal.get(
                    "best_match_blockers",
                    [],
                )
                or []
            )

            near_market_raise_fit.extend(
                market_signal.get(
                    "what_would_raise_fit",
                    [],
                )
                or []
            )

    return {
        "sample_size": len(signals),
        "competitive_sample_size": competitive_jobs,
        "near_market_sample_size": near_market_jobs,

        "recommendations": dict(
            recommendation_counter
        ),

        "average_fit": (
            round(
                sum(fit_scores)
                / len(fit_scores),
                1,
            )
            if fit_scores
            else None
        ),

        "role_families": _top_signals(
            competitive_roles,
            limit=5,
        ),

        "best_match_blockers": _top_signals(
            near_market_blockers,
            limit=7,
        ),

        "market_strengths": _top_signals(
            competitive_strengths,
            limit=7,
        ),

        "what_would_raise_fit": _top_signals(
            near_market_raise_fit,
            limit=7,
        ),
    }


def load_historical_market_signals(
    candidate_id: str,
) -> list[dict[str, Any]]:
    signals = []

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                job_id,
                recommendation,
                current_fit,
                analysis_json
            FROM candidate_job_analyses
            WHERE candidate_id = ?
              AND recommendation IS NOT NULL
            ORDER BY updated_at DESC
            """,
            (
                candidate_id,
            ),
        ).fetchall()

    for row in rows:
        try:
            analysis = json.loads(
                row["analysis_json"]
                or "{}"
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            continue

        market_signal = analysis.get(
            "market_signal"
        )

        if not isinstance(
            market_signal,
            dict,
        ):
            continue

        if not market_signal:
            continue

        signals.append(
            {
                "job_id": row["job_id"],
                "recommendation": (
                    row["recommendation"]
                ),
                "current_fit": (
                    row["current_fit"]
                ),
                "market_signal": (
                    market_signal
                ),
            }
        )

    return signals


def build_market_position(
    candidate_id: str,
    batch_signals: list[
        dict[str, Any]
    ] | None = None,
) -> dict[str, Any]:
    batch_signals = (
        batch_signals or []
    )

    historical_signals = (
        load_historical_market_signals(
            candidate_id
        )
    )

    return {
        "current_batch": _aggregate(
            batch_signals
        ),
        "historical": _aggregate(
            historical_signals
        ),
    }
