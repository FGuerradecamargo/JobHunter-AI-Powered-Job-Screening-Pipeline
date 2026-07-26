import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_FILE = Path("data/jobhunter.db")

VALID_STATUSES = {
    "in_review",
    "applied",
    "rejected",
}


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def get_connection() -> sqlite3.Connection:
    DATABASE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                url TEXT,
                status TEXT NOT NULL DEFAULT 'in_review',
                recommendation TEXT,
                competitive_status TEXT,
                current_fit INTEGER,
                growth_value INTEGER,
                analysis_json TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                applied_at TEXT,
                rejected_at TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON jobs(status)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_company
            ON jobs(company)
            """
        )


def upsert_recommendation(
    item: dict[str, Any],
) -> None:
    job = item.get("job", {})
    analysis = item.get("analysis", {})

    job_id = str(
        job.get("id", "")
    ).strip()

    if not job_id:
        return

    now = utc_now()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id,
                title,
                company,
                location,
                url,
                status,
                recommendation,
                competitive_status,
                current_fit,
                growth_value,
                analysis_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                location = excluded.location,
                url = excluded.url,
                recommendation = excluded.recommendation,
                competitive_status = excluded.competitive_status,
                current_fit = excluded.current_fit,
                growth_value = excluded.growth_value,
                analysis_json = excluded.analysis_json,
                updated_at = excluded.updated_at
            """,
            (
                job_id,
                job.get(
                    "title",
                    "Untitled role",
                ),
                job.get("company"),
                job.get("location"),
                job.get("url"),
                "in_review",
                analysis.get(
                    "recommendation"
                ),
                analysis.get(
                    "competitive_status"
                ),
                analysis.get(
                    "current_fit"
                ),
                analysis.get(
                    "growth_value"
                ),
                json.dumps(
                    analysis,
                    ensure_ascii=False,
                ),
                now,
                now,
            ),
        )


def import_recommendations(
    recommendations: list[dict[str, Any]],
) -> int:
    imported = 0

    for item in recommendations:
        analysis = item.get(
            "analysis",
            {},
        )

        recommendation = analysis.get(
            "recommendation"
        )

        hard_conflicts = analysis.get(
            "hard_conflicts",
            [],
        )

        if recommendation not in {
            "recommended_apply",
            "worth_second_look",
        }:
            continue

        if hard_conflicts:
            continue

        upsert_recommendation(item)
        imported += 1

    return imported


def list_jobs(
    status: str,
) -> list[dict[str, Any]]:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status}"
        )

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = ?
            ORDER BY
                growth_value DESC,
                current_fit DESC,
                created_at DESC
            """,
            (status,),
        ).fetchall()

    jobs: list[dict[str, Any]] = []

    for row in rows:
        item = dict(row)

        item["analysis"] = json.loads(
            item.pop("analysis_json")
        )

        jobs.append(item)

    return jobs


def count_jobs_by_status() -> dict[str, int]:
    counts = {
        "in_review": 0,
        "applied": 0,
        "rejected": 0,
    }

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM jobs
            GROUP BY status
            """
        ).fetchall()

    for row in rows:
        counts[row["status"]] = row["total"]

    return counts


def update_job_status(
    job_id: str,
    status: str,
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status}"
        )

    now = utc_now()

    applied_at = (
        now
        if status == "applied"
        else None
    )

    rejected_at = (
        now
        if status == "rejected"
        else None
    )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET
                status = ?,
                updated_at = ?,
                applied_at = COALESCE(
                    ?,
                    applied_at
                ),
                rejected_at = COALESCE(
                    ?,
                    rejected_at
                )
            WHERE id = ?
            """,
            (
                status,
                now,
                applied_at,
                rejected_at,
                job_id,
            ),
        )


def update_job_notes(
    job_id: str,
    notes: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                notes,
                utc_now(),
                job_id,
            ),
        )