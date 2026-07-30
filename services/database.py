from models.job import Job

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


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

        jobs_columns = connection.execute(
            """
            PRAGMA table_info(jobs)
            """
        ).fetchall()

        jobs_column_names = {
            column["name"]
            for column in jobs_columns
        }

        jobs_new_columns = {
            "raw_text": "TEXT",
            "remote": "INTEGER",
            "salary": "TEXT",
            "easy_apply": "INTEGER NOT NULL DEFAULT 0",
        }

        for column_name, column_type in jobs_new_columns.items():
            if column_name not in jobs_column_names:
                connection.execute(
                    f"""
                    ALTER TABLE jobs
                    ADD COLUMN {column_name} {column_type}
                    """
                )

        gmail_message_columns = connection.execute(
            """
            PRAGMA table_info(gmail_messages)
            """
        ).fetchall()

        gmail_message_column_names = {
            column["name"]
            for column in gmail_message_columns
        }

        gmail_message_new_columns = {
            "subject": "TEXT",
            "sender": "TEXT",
            "snippet": "TEXT",
            "raw_html": "TEXT",
            "content_fetched_at": "TEXT",
        }

        for column_name, column_type in (
                gmail_message_new_columns.items()
        ):
            if column_name not in gmail_message_column_names:
                connection.execute(
                    f"""
                    ALTER TABLE gmail_messages
                    ADD COLUMN {column_name} {column_type}
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
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                candidate_id TEXT UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE SET NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gmail_connections (
                user_id TEXT PRIMARY KEY,
                gmail_address TEXT NOT NULL UNIQUE,
                encrypted_refresh_token TEXT NOT NULL,
                access_token TEXT,
                token_expiry TEXT,
                scopes_json TEXT NOT NULL,
                last_history_id TEXT,
                last_sync_at TEXT,
                connection_status TEXT NOT NULL DEFAULT 'connected',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gmail_messages (
                user_id TEXT NOT NULL,
                gmail_message_id TEXT NOT NULL,
                gmail_thread_id TEXT,
                received_at TEXT,
                processed_at TEXT,
                processing_status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT NOT NULL,

                PRIMARY KEY (
                    user_id,
                    gmail_message_id
                ),

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
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
                idx_users_candidate_id
            ON users(candidate_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_gmail_messages_status
            ON gmail_messages(
                user_id,
                processing_status
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_gmail_messages_received_at
            ON gmail_messages(
                user_id,
                received_at
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

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_authorization_states (
                state TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                code_verifier TEXT NOT NULL,
                created_at TEXT NOT NULL,
                consumed_at TEXT,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        columns = connection.execute(
            """
            PRAGMA table_info(oauth_authorization_states)
            """
        ).fetchall()

        column_names = {
            column["name"]
            for column in columns
        }

        if "code_verifier" not in column_names:
            connection.execute(
                """
                ALTER TABLE oauth_authorization_states
                ADD COLUMN code_verifier TEXT
                """
            )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_oauth_states_user_id
            ON oauth_authorization_states(user_id)
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
                raw_text,
                title,
                company,
                location,
                url,
                remote,
                salary,
                easy_apply,
                analysis_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

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

def upsert_raw_job(
        job: Job,
) -> str:
    """
    Insere uma vaga nova no pool compartilhado.

    Se a vaga já existir, atualiza apenas quando o novo
    raw_text possui mais informações.
    """
    job_id = str(job.id).strip()

    if not job_id:
        raise ValueError(
            "Job ID is required."
        )

    now = utc_now()

    with get_connection() as connection:
        existing_row = connection.execute(
            """
            SELECT
                id,
                raw_text
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if existing_row is None:
            connection.execute(
                """
                INSERT INTO jobs (
                    id,
                    raw_text,
                    title,
                    company,
                    location,
                    url,
                    remote,
                    salary,
                    easy_apply,
                    analysis_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    job.raw_text,
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.remote,
                    job.salary,
                    job.easy_apply,
                    "{}",
                    now,
                    now,
                ),
            )

            return "created"

        current_raw_text = (
                existing_row["raw_text"]
                or ""
        )

        new_raw_text = job.raw_text or ""

        if len(new_raw_text) <= len(
                current_raw_text
        ):
            return "unchanged"

        connection.execute(
            """
            UPDATE jobs
            SET
                raw_text = ?,
                title = COALESCE(?, title),
                company = COALESCE(?, company),
                location = COALESCE(?, location),
                url = COALESCE(?, url),
                remote = COALESCE(?, remote),
                salary = COALESCE(?, salary),
                easy_apply = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                new_raw_text,
                job.title,
                job.company,
                job.location,
                job.url,
                job.remote,
                job.salary,
                job.easy_apply,
                now,
                job_id,
            ),
        )

        return "updated"


def ensure_candidate_job_analysis(
        candidate_id: str,
        job_id: str,
) -> bool:
    """
    Cria a relação candidato-vaga caso ela ainda não exista.

    A análise real será preenchida posteriormente.
    """
    if not candidate_id:
        raise ValueError(
            "Candidate ID is required."
        )

    if not job_id:
        raise ValueError(
            "Job ID is required."
        )

    now = utc_now()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO candidate_job_analyses (
                candidate_id,
                job_id,
                recommendation,
                competitive_status,
                current_fit,
                growth_value,
                analysis_json,
                status,
                notes,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                NULL,
                NULL,
                NULL,
                NULL,
                '{}',
                'in_review',
                '',
                ?,
                ?
            )
            """,
            (
                candidate_id,
                job_id,
                now,
                now,
            ),
        )

    return cursor.rowcount > 0