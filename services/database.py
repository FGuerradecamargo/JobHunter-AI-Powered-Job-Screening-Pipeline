from functools import lru_cache
from contextlib import contextmanager
from models.job import Job

import json
from services.analysis_signatures import build_job_signature_from_values
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from services.job_category_service import (
    JobCategoryService,
)

import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()


DATABASE_FILE = Path("data/jobhunter.db")

VALID_STATUSES = {
    "system_rejected",
    "in_review",
    "user_rejected",
    "applied",
    "rejected_before_interview",
    "in_process",
    "rejected_after_interview",
    "offer",
}

APPLICATION_STATUSES = {
    "applied",
    "rejected_before_interview",
    "in_process",
    "rejected_after_interview",
    "offer",
}

COMPANY_REJECTION_STATUSES = {
    "rejected_before_interview",
    "rejected_after_interview",
}


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


@lru_cache(maxsize=1)
def _get_postgres_pool(
    database_url: str,
) -> ConnectionPool:
    return ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=5,
        kwargs={
            "row_factory": dict_row,
        },
        check=ConnectionPool.check_connection,
        max_idle=60,
        open=True,
    )


@contextmanager
def get_connection():
    database_url = os.getenv(
        "DATABASE_URL"
    )

    if database_url:
        pool = _get_postgres_pool(
            database_url
        )

        with pool.connection() as connection:
            yield PostgresConnectionAdapter(
                connection
            )

        return

    DATABASE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:
        with connection:
            yield connection
    finally:
        connection.close()


def is_postgres() -> bool:
    return bool(
        os.getenv("DATABASE_URL")
    )


def initialize_postgres_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                "current_role" TEXT NOT NULL,
                current_level TEXT NOT NULL,
                professional_summary TEXT NOT NULL,

                target_roles_json TEXT NOT NULL,
                spoken_languages_json TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                strengths_json TEXT NOT NULL,
                development_areas_json TEXT NOT NULL,
                preferences_json TEXT NOT NULL,
                constraints_json TEXT NOT NULL,
                priorities_json TEXT NOT NULL DEFAULT '[]',

                professional_experiences_json TEXT NOT NULL DEFAULT '[]',
                proven_capabilities_json TEXT NOT NULL DEFAULT '[]',
                transferable_capabilities_json TEXT NOT NULL DEFAULT '[]',
                developing_capabilities_json TEXT NOT NULL DEFAULT '[]',
                technical_tools_json TEXT NOT NULL DEFAULT '[]',
                domain_experience_json TEXT NOT NULL DEFAULT '[]',
                competitive_role_families_json TEXT NOT NULL DEFAULT '[]',
                bridge_role_families_json TEXT NOT NULL DEFAULT '[]',
                target_role_families_json TEXT NOT NULL DEFAULT '[]',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            ALTER TABLE candidates
            ADD COLUMN IF NOT EXISTS priorities_json
            TEXT NOT NULL DEFAULT '[]'
            """
        )

        for column_name in (
            "professional_experiences_json",
            "proven_capabilities_json",
            "transferable_capabilities_json",
            "developing_capabilities_json",
            "technical_tools_json",
            "domain_experience_json",
            "competitive_role_families_json",
            "bridge_role_families_json",
            "target_role_families_json",
        ):
            connection.execute(
                f'''
                ALTER TABLE candidates
                ADD COLUMN IF NOT EXISTS {column_name}
                TEXT NOT NULL DEFAULT '[]'
                '''
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_career_updates (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                update_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_career_objectives (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                desired_role_families_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_objective_profiles (
                objective_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                profile_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (objective_id)
                    REFERENCES candidate_career_objectives(id)
                    ON DELETE CASCADE
            )
            """
        )

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
                analysis_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT NOT NULL DEFAULT '',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                applied_at TEXT,
                rejected_at TEXT,

                raw_text TEXT,
                remote INTEGER,
                salary TEXT,
                easy_apply INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                category TEXT,
                sub_category TEXT
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
                access_level TEXT NOT NULL DEFAULT 'user',
                password_hash TEXT,
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
            CREATE TABLE IF NOT EXISTS candidate_job_analyses (
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,

                recommendation TEXT,
                competitive_status TEXT,
                current_fit INTEGER,
                growth_value INTEGER,

                analysis_json TEXT NOT NULL DEFAULT '{}',
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

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (job_id)
                    REFERENCES jobs(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS job_sources (
                job_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                discovered_at TEXT NOT NULL,

                PRIMARY KEY (
                    job_id,
                    user_id,
                    source_type
                ),

                FOREIGN KEY (job_id)
                    REFERENCES jobs(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
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

                subject TEXT,
                sender TEXT,
                snippet TEXT,
                raw_html TEXT,
                content_fetched_at TEXT,

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

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_onboarding (
                candidate_id TEXT PRIMARY KEY,
                location TEXT NOT NULL DEFAULT '',
                work_authorisation TEXT NOT NULL DEFAULT '',
                spoken_languages_json TEXT NOT NULL DEFAULT '[]',
                desired_next_work TEXT NOT NULL DEFAULT '',
                enjoyed_work TEXT NOT NULL DEFAULT '',
                avoid_work TEXT NOT NULL DEFAULT '',
                development_interests TEXT NOT NULL DEFAULT '',
                career_priorities_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_work_experiences (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                company TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                career_story TEXT NOT NULL,
                day_to_day_narrative TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_job_sources_user_id
            ON job_sources(user_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_job_sources_job_id
            ON job_sources(job_id)
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
            CREATE INDEX IF NOT EXISTS
                idx_candidate_work_experiences_candidate_id
            ON candidate_work_experiences(candidate_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_oauth_states_user_id
            ON oauth_authorization_states(user_id)
            """
        )


        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            candidate_application_outcomes (
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,

                final_status TEXT NOT NULL DEFAULT '',
                interview_stage TEXT NOT NULL DEFAULT '',
                rejection_reason TEXT NOT NULL DEFAULT '',
                recruiter_feedback TEXT NOT NULL DEFAULT '',
                candidate_notes TEXT NOT NULL DEFAULT '',

                offer_salary TEXT NOT NULL DEFAULT '',
                offer_currency TEXT NOT NULL DEFAULT '',

                lessons_learned TEXT NOT NULL DEFAULT '',

                outcome_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                PRIMARY KEY (
                    candidate_id,
                    job_id
                ),

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (job_id)
                    REFERENCES jobs(id)
                    ON DELETE CASCADE
            )
            """
        )


        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            candidate_career_development (
                candidate_id TEXT PRIMARY KEY,

                context_signature TEXT NOT NULL,
                recommendation_json TEXT NOT NULL DEFAULT '{}',
                analysis_version TEXT NOT NULL,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )


class PostgresConnectionAdapter:
    def __init__(self, connection):
        self._connection = connection

    def execute(
        self,
        query: str,
        params=None,
    ):
        if params is not None:
            query = query.replace(
                "?",
                "%s",
            )

        return self._connection.execute(
            query,
            params,
        )

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return self._connection.__exit__(
            exc_type,
            exc_value,
            traceback,
        )

    def close(self):
        return self._connection.close()


def initialize_sqlite_database() -> None:
    with get_connection() as connection:
        # ==================================================
        # Base tables
        # ==================================================

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
                priorities_json TEXT NOT NULL DEFAULT '[]',

                professional_experiences_json TEXT NOT NULL DEFAULT '[]',
                proven_capabilities_json TEXT NOT NULL DEFAULT '[]',
                transferable_capabilities_json TEXT NOT NULL DEFAULT '[]',
                developing_capabilities_json TEXT NOT NULL DEFAULT '[]',
                technical_tools_json TEXT NOT NULL DEFAULT '[]',
                domain_experience_json TEXT NOT NULL DEFAULT '[]',
                competitive_role_families_json TEXT NOT NULL DEFAULT '[]',
                bridge_role_families_json TEXT NOT NULL DEFAULT '[]',
                target_role_families_json TEXT NOT NULL DEFAULT '[]',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        candidate_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(candidates)"
            ).fetchall()
        }

        for column_name in (
            "professional_experiences_json",
            "proven_capabilities_json",
            "transferable_capabilities_json",
            "developing_capabilities_json",
            "technical_tools_json",
            "domain_experience_json",
            "competitive_role_families_json",
            "bridge_role_families_json",
            "target_role_families_json",
        ):
            if column_name not in candidate_columns:
                connection.execute(
                    f'''
                    ALTER TABLE candidates
                    ADD COLUMN {column_name}
                    TEXT NOT NULL DEFAULT '[]'
                    '''
                )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_career_updates (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                update_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_career_objectives (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                desired_role_families_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_objective_profiles (
                objective_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                profile_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (objective_id)
                    REFERENCES candidate_career_objectives(id)
                    ON DELETE CASCADE
            )
            """
        )

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
                analysis_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT NOT NULL DEFAULT '',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                applied_at TEXT,
                rejected_at TEXT,

                raw_text TEXT,
                remote INTEGER,
                salary TEXT,
                easy_apply INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                category TEXT,
                sub_category TEXT
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
                access_level TEXT NOT NULL DEFAULT 'user',
                password_hash TEXT,
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
            CREATE TABLE IF NOT EXISTS candidate_job_analyses (
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,

                recommendation TEXT,
                competitive_status TEXT,
                current_fit INTEGER,
                growth_value INTEGER,

                analysis_json TEXT NOT NULL DEFAULT '{}',
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

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (job_id)
                    REFERENCES jobs(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS job_sources (
                job_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                discovered_at TEXT NOT NULL,

                PRIMARY KEY (
                    job_id,
                    user_id,
                    source_type
                ),

                FOREIGN KEY (job_id)
                    REFERENCES jobs(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
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

                subject TEXT,
                sender TEXT,
                snippet TEXT,
                raw_html TEXT,
                content_fetched_at TEXT,

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

        # ==================================================
        # Migrations for existing databases
        # ==================================================

        users_columns = connection.execute(
            """
            PRAGMA table_info(users)
            """
        ).fetchall()

        users_column_names = {
            column["name"]
            for column in users_columns
        }

        if "access_level" not in users_column_names:
            connection.execute(
                """
                ALTER TABLE users
                ADD COLUMN access_level TEXT
                NOT NULL DEFAULT 'user'
                """
            )

        if "password_hash" not in users_column_names:
            connection.execute(
                """
                ALTER TABLE users
                ADD COLUMN password_hash TEXT
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
            "description": "TEXT",
            "category": "TEXT",
            "sub_category": "TEXT",
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
            UPDATE candidate_job_analyses
            SET
                status = 'system_rejected',
                updated_at = ?
            WHERE status = 'rejected'
            """,
            (utc_now(),),
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
                idx_job_sources_user_id
            ON job_sources(user_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_job_sources_job_id
            ON job_sources(job_id)
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

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_onboarding (
                candidate_id TEXT PRIMARY KEY,
                location TEXT NOT NULL DEFAULT '',
                work_authorisation TEXT NOT NULL DEFAULT '',
                spoken_languages_json TEXT NOT NULL DEFAULT '[]',
                desired_next_work TEXT NOT NULL DEFAULT '',
                enjoyed_work TEXT NOT NULL DEFAULT '',
                avoid_work TEXT NOT NULL DEFAULT '',
                development_interests TEXT NOT NULL DEFAULT '',
                career_priorities_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_work_experiences (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                company TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                career_story TEXT NOT NULL,
                day_to_day_narrative TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_candidate_work_experiences_candidate_id
            ON candidate_work_experiences(candidate_id)
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


@lru_cache(maxsize=1)
def initialize_database() -> None:
    if is_postgres():
        initialize_postgres_database()
        return

    initialize_sqlite_database()


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

    category_service = JobCategoryService()

    job_category = category_service.classify(
        title=job.title or "",
        description=getattr(
            job,
            "description",
            "",
        ) or "",
        raw_text=job.raw_text or "",
    )

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
                category,
                sub_category,
                analysis_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

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
        "system_rejected": 0,
        "in_review": 0,
        "user_rejected": 0,
        "applied": 0,
        "rejected_before_interview": 0,
        "in_process": 0,
        "rejected_after_interview": 0,
        "offer": 0,
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
        if status in APPLICATION_STATUSES
        else None
    )

    rejected_at = (
        now
        if status in COMPANY_REJECTION_STATUSES
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
                AND (
                    ? != 'in_review'
                    OR candidate_job_analyses.recommendation
                        IS NOT NULL
                )

            ORDER BY
                candidate_job_analyses.growth_value DESC,
                candidate_job_analyses.current_fit DESC,
                candidate_job_analyses.created_at DESC
            """,
            (
                candidate_id,
                status,
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
        "system_rejected": 0,
        "in_review": 0,
        "user_rejected": 0,
        "applied": 0,
        "rejected_before_interview": 0,
        "in_process": 0,
        "rejected_after_interview": 0,
        "offer": 0,
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
        if status in APPLICATION_STATUSES
        else None
    )

    rejected_at = (
        now
        if status in COMPANY_REJECTION_STATUSES
        else None
    )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE candidate_job_analyses
            SET
                status = ?,
                updated_at = ?,
                applied_at = COALESCE(?, applied_at),
                rejected_at = COALESCE(?, rejected_at)
            WHERE
                candidate_id = ?
                AND job_id = ?
            """,
            (
                status,
                now,
                applied_at,
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

    category_service = JobCategoryService()

    job_category = category_service.classify(
        title=job.title or "",
        description=getattr(
            job,
            "description",
            "",
        ) or "",
        raw_text=job.raw_text or "",
    )

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
                    category,
                    sub_category,
                    analysis_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    job.raw_text,
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    (
                        None
                        if job.remote is None
                        else int(job.remote)
                    ),
                    job.salary,
                    int(job.easy_apply),
                    job_category.category,
                    job_category.sub_category,
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
                category = ?,
                sub_category = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                new_raw_text,
                job.title,
                job.company,
                job.location,
                job.url,
                (
                    None
                    if job.remote is None
                    else int(job.remote)
                ),
                job.salary,
                int(job.easy_apply),
                job_category.category,
                job_category.sub_category,
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

    Também evita que o mesmo candidato receba novamente uma
    vaga equivalente com outro job ID, considerando título,
    empresa e localização normalizados.
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
        job_row = connection.execute(
            """
            SELECT
                id,
                title,
                company,
                location
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if job_row is None:
            raise ValueError(
                f"Job was not found: {job_id}"
            )

        equivalent_row = connection.execute(
            """
            SELECT
                candidate_job_analyses.job_id

            FROM candidate_job_analyses

            INNER JOIN jobs
                ON jobs.id = candidate_job_analyses.job_id

            WHERE
                candidate_job_analyses.candidate_id = ?

                AND LOWER(
                    TRIM(
                        COALESCE(jobs.title, '')
                    )
                ) = LOWER(
                    TRIM(
                        COALESCE(?, '')
                    )
                )

                AND LOWER(
                    TRIM(
                        COALESCE(jobs.company, '')
                    )
                ) = LOWER(
                    TRIM(
                        COALESCE(?, '')
                    )
                )

                AND LOWER(
                    TRIM(
                        COALESCE(jobs.location, '')
                    )
                ) = LOWER(
                    TRIM(
                        COALESCE(?, '')
                    )
                )

            LIMIT 1
            """,
            (
                candidate_id,
                job_row["title"],
                job_row["company"],
                job_row["location"],
            ),
        ).fetchone()

        if equivalent_row is not None:
            return False

        cursor = connection.execute(
            """
            INSERT INTO candidate_job_analyses (
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


def list_pending_candidate_jobs(
    candidate_id: str,
    limit: int = 5,
    analysis_version: str | None = None,
    candidate_signature: str | None = None,
) -> list[dict[str, Any]]:
    if not candidate_id:
        raise ValueError(
            "Candidate ID is required."
        )

    if limit <= 0:
        raise ValueError(
            "Limit must be greater than zero."
        )

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                jobs.id,
                jobs.raw_text,
                jobs.url,
                jobs.title,
                jobs.company,
                jobs.location,
                jobs.remote,
                jobs.salary,
                jobs.easy_apply,
                jobs.description,

                candidate_job_analyses.analysis_version,
                candidate_job_analyses.candidate_signature,
                candidate_job_analyses.job_signature,
                candidate_job_analyses.recommendation,
                candidate_job_analyses.status,
                candidate_job_analyses.created_at

            FROM candidate_job_analyses

            INNER JOIN jobs
                ON jobs.id =
                    candidate_job_analyses.job_id

            WHERE
                candidate_job_analyses.candidate_id = ?

                AND candidate_job_analyses.status IN (
                    'in_review',
                    'system_rejected'
                )

            ORDER BY
                candidate_job_analyses.created_at ASC
            """,
            (
                candidate_id,
            ),
        ).fetchall()

    pending_rows: list[dict[str, Any]] = []

    for row in rows:
        row_dict = dict(row)

        stored_analysis_version = (
            row_dict.get("analysis_version")
        )

        stored_candidate_signature = (
            row_dict.get("candidate_signature")
        )

        stored_job_signature = (
            row_dict.get("job_signature")
        )

        current_job_signature = (
            build_job_signature_from_values(
                job_id=row_dict.get("id"),
                title=row_dict.get("title"),
                company=row_dict.get("company"),
                location=row_dict.get("location"),
                remote=row_dict.get("remote"),
                salary=row_dict.get("salary"),
                description=row_dict.get(
                    "description"
                ),
                url=row_dict.get("url"),
            )
        )

        needs_analysis = (
            row_dict.get("recommendation") is None
            or (
                stored_analysis_version or ""
            ) != (
                analysis_version or ""
            )
            or (
                stored_candidate_signature or ""
            ) != (
                candidate_signature or ""
            )
            or (
                stored_job_signature or ""
            ) != current_job_signature
        )

        if not needs_analysis:
            continue

        pending_rows.append(row_dict)

        if len(pending_rows) >= limit:
            break

    return pending_rows


def update_shared_job_analysis_data(
    job: Job,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET
                description = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                job.description,
                utc_now(),
                str(job.id),
            ),
        )


def save_candidate_job_analysis(
    candidate_id: str,
    job_id: str,
    analysis: dict[str, Any],
    job_signature: str,
    candidate_signature: str,
    analysis_version: str,
    status: str = "in_review",
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status}"
        )

    recommendation = analysis.get(
        "recommendation"
    )

    competitive_status = analysis.get(
        "competitive_status"
    )

    current_fit = analysis.get(
        "current_fit"
    )

    growth_value = analysis.get(
        "growth_value"
    )

    now = utc_now()

    rejected_at = (
        now
        if status == "rejected"
        else None
    )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE candidate_job_analyses

            SET
                recommendation = ?,
                competitive_status = ?,
                current_fit = ?,
                growth_value = ?,
                analysis_json = ?,
                job_signature = ?,
                candidate_signature = ?,
                analysis_version = ?,
                status = ?,
                rejected_at = ?,
                updated_at = ?

            WHERE
                candidate_id = ?
                AND job_id = ?
            """,
            (
                recommendation,
                competitive_status,
                current_fit,
                growth_value,
                json.dumps(
                    analysis,
                    ensure_ascii=False,
                ),
                job_signature,
                candidate_signature,
                analysis_version,
                status,
                rejected_at,
                now,
                candidate_id,
                job_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError(
                "Candidate-job relationship was not found: "
                f"{candidate_id} / {job_id}"
            )

def save_candidate_application_outcome(
    candidate_id: str,
    job_id: str,
    final_status: str = "",
    interview_stage: str = "",
    rejection_reason: str = "",
    recruiter_feedback: str = "",
    candidate_notes: str = "",
    offer_salary: str = "",
    offer_currency: str = "",
    lessons_learned: str = "",
    outcome_date: str | None = None,
) -> None:
    now = utc_now()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO candidate_application_outcomes (
                candidate_id,
                job_id,
                final_status,
                interview_stage,
                rejection_reason,
                recruiter_feedback,
                candidate_notes,
                offer_salary,
                offer_currency,
                lessons_learned,
                outcome_date,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(candidate_id, job_id)
            DO UPDATE SET
                final_status = excluded.final_status,
                interview_stage = excluded.interview_stage,
                rejection_reason = excluded.rejection_reason,
                recruiter_feedback = excluded.recruiter_feedback,
                candidate_notes = excluded.candidate_notes,
                offer_salary = excluded.offer_salary,
                offer_currency = excluded.offer_currency,
                lessons_learned = excluded.lessons_learned,
                outcome_date = excluded.outcome_date,
                updated_at = excluded.updated_at
            """,
            (
                candidate_id,
                job_id,
                final_status,
                interview_stage,
                rejection_reason,
                recruiter_feedback,
                candidate_notes,
                offer_salary,
                offer_currency,
                lessons_learned,
                outcome_date,
                now,
                now,
            ),
        )


def get_candidate_application_outcome(
    candidate_id: str,
    job_id: str,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM candidate_application_outcomes
            WHERE candidate_id = ?
              AND job_id = ?
            """,
            (
                candidate_id,
                job_id,
            ),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def list_candidate_application_outcomes(
    candidate_id: str,
) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                outcomes.candidate_id,
                outcomes.job_id,
                outcomes.final_status,
                outcomes.interview_stage,
                outcomes.rejection_reason,
                outcomes.recruiter_feedback,
                outcomes.candidate_notes,
                outcomes.offer_salary,
                outcomes.offer_currency,
                outcomes.lessons_learned,
                outcomes.outcome_date,
                outcomes.created_at,
                outcomes.updated_at,

                jobs.title,
                jobs.company,
                jobs.location,

                candidate_job_analyses.recommendation,
                candidate_job_analyses.competitive_status,
                candidate_job_analyses.current_fit,
                candidate_job_analyses.growth_value,
                candidate_job_analyses.analysis_json

            FROM candidate_application_outcomes AS outcomes

            INNER JOIN jobs
                ON jobs.id = outcomes.job_id

            INNER JOIN candidate_job_analyses
                ON candidate_job_analyses.candidate_id =
                    outcomes.candidate_id
                AND candidate_job_analyses.job_id =
                    outcomes.job_id

            WHERE outcomes.candidate_id = ?

            ORDER BY outcomes.updated_at DESC
            """,
            (
                candidate_id,
            ),
        ).fetchall()

    results: list[dict[str, Any]] = []

    for row in rows:
        item = dict(row)

        analysis_json = item.pop(
            "analysis_json",
            "{}",
        )

        try:
            item["analysis"] = json.loads(
                analysis_json or "{}"
            )
        except (TypeError, json.JSONDecodeError):
            item["analysis"] = {}

        results.append(item)

    return results

def get_candidate_career_development(
    candidate_id: str,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM candidate_career_development
            WHERE candidate_id = ?
            """,
            (
                candidate_id,
            ),
        ).fetchone()

    if row is None:
        return None

    item = dict(row)

    try:
        item["recommendation"] = json.loads(
            item.pop(
                "recommendation_json",
                "{}",
            )
            or "{}"
        )
    except (
        TypeError,
        json.JSONDecodeError,
    ):
        item["recommendation"] = {}

    return item


def save_candidate_career_development(
    candidate_id: str,
    context_signature: str,
    recommendation: dict[str, Any],
    analysis_version: str,
) -> None:
    now = utc_now()

    recommendation_json = json.dumps(
        recommendation,
        ensure_ascii=False,
    )

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO candidate_career_development (
                candidate_id,
                context_signature,
                recommendation_json,
                analysis_version,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(candidate_id)
            DO UPDATE SET
                context_signature =
                    excluded.context_signature,
                recommendation_json =
                    excluded.recommendation_json,
                analysis_version =
                    excluded.analysis_version,
                updated_at =
                    excluded.updated_at
            """,
            (
                candidate_id,
                context_signature,
                recommendation_json,
                analysis_version,
                now,
                now,
            ),
        )

