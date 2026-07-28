import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_FILE = Path("data/jobhunter.db")

VALID_STATUSES = {
    "in_review",
    "applied",
    "in_process",
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

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                current_role TEXT NOT NULL,
                current_level TEXT NOT NULL,
                professional_summary TEXT NOT NULL,
                target_roles_json TEXT NOT NULL,
                spoken_languages_json TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                strengths_json TEXT NOT NULL,
                development_areas_json TEXT NOT NULL,
                preferences_json TEXT NOT NULL,
                constraints_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_job_analyses (
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                recommendation TEXT,
                competitive_status TEXT,
                current_fit INTEGER,
                growth_value INTEGER,
                analysis_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_review',
                notes TEXT NOT NULL DEFAULT '',
                job_signature TEXT,
                candidate_signature TEXT,
                analysis_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                applied_at TEXT,
                rejected_at TEXT,

                PRIMARY KEY (
                    candidate_id,
                    job_id
                ),

                FOREIGN KEY (
                    candidate_id
                )
                REFERENCES candidates(id)
                ON DELETE CASCADE,

                FOREIGN KEY (
                    job_id
                )
                REFERENCES jobs(id)
                ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_candidate_job_status
            ON candidate_job_analyses(
                candidate_id,
                status
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_candidate_job_fit
            ON candidate_job_analyses(
                candidate_id,
                current_fit
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_candidate_job_growth
            ON candidate_job_analyses(
                candidate_id,
                growth_value
            )
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


def list_candidate_jobs(
    candidate_id: str,
    status: str,
) -> list[dict[str, Any]]:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status}"
        )

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                jobs.id,
                jobs.title,
                jobs.company,
                jobs.location,
                jobs.url,

                candidate_job_analyses.status,
                candidate_job_analyses.notes,
                candidate_job_analyses.recommendation,
                candidate_job_analyses.competitive_status,
                candidate_job_analyses.current_fit,
                candidate_job_analyses.growth_value,
                candidate_job_analyses.analysis_json,
                candidate_job_analyses.created_at,
                candidate_job_analyses.updated_at,
                candidate_job_analyses.applied_at,
                candidate_job_analyses.rejected_at

            FROM candidate_job_analyses

            INNER JOIN jobs
                ON jobs.id = candidate_job_analyses.job_id

            WHERE
                candidate_job_analyses.candidate_id = ?
                AND candidate_job_analyses.status = ?

            ORDER BY
                candidate_job_analyses.growth_value DESC,
                candidate_job_analyses.current_fit DESC,
                candidate_job_analyses.created_at DESC
            """,
            (
                candidate_id,
                status,
            ),
        ).fetchall()

    results: list[dict[str, Any]] = []

    for row in rows:
        item = dict(row)

        item["analysis"] = json.loads(
            item.pop("analysis_json")
        )

        results.append(item)

    return results


def count_candidate_jobs_by_status(
    candidate_id: str,
) -> dict[str, int]:
    counts = {
        "in_review": 0,
        "applied": 0,
        "in_process": 0,
        "rejected": 0,
    }

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                status,
                COUNT(*) AS total

            FROM candidate_job_analyses

            WHERE candidate_id = ?

            GROUP BY status
            """,
            (candidate_id,),
        ).fetchall()

    for row in rows:
        counts[row["status"]] = row["total"]

    return counts


def update_candidate_job_status(
    candidate_id: str,
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
            UPDATE candidate_job_analyses

            SET
                status = ?,
                updated_at = ?,

                applied_at = CASE
                    WHEN ? IS NOT NULL
                    THEN ?
                    ELSE applied_at
                END,

                rejected_at = CASE
                    WHEN ? IS NOT NULL
                    THEN ?
                    ELSE rejected_at
                END

            WHERE
                candidate_id = ?
                AND job_id = ?
            """,
            (
                status,
                now,
                applied_at,
                applied_at,
                rejected_at,
                rejected_at,
                candidate_id,
                job_id,
            ),
        )


def update_candidate_job_notes(
    candidate_id: str,
    job_id: str,
    notes: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE candidate_job_analyses

            SET
                notes = ?,
                updated_at = ?

            WHERE
                candidate_id = ?
                AND job_id = ?
            """,
            (
                notes,
                utc_now(),
                candidate_id,
                job_id,
            ),
        )