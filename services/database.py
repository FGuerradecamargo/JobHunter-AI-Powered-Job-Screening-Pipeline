from functools import lru_cache
from contextlib import contextmanager
from models.job import Job

import json
from services.analysis_signatures import build_job_signature_from_values
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

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


VALID_OPPORTUNITY_STATES = {
    "none",
    "active",
    "user_rejected",
    "applied",
    "rejected_before_interview",
    "in_process",
    "rejected_after_interview",
    "offer",
    "expired",
}


APPROVED_OPPORTUNITY_RECOMMENDATIONS = {
    "best_match",
    "potential",
    "good_opportunity",

    # Legacy compatibility.
    "apply",
    "recommended_apply",
    "worth_second_look",
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


class CandidateJobAnalysisClaimLostError(RuntimeError):
    """
    Raised when a worker tries to persist an analysis after
    losing ownership of the candidate-job analysis lease.
    """


def _ensure_candidate_job_analysis_claim_columns(
    connection,
) -> None:
    """
    Add infrastructure-only candidate-job analysis lease
    columns without changing lifecycle state semantics.
    """
    claim_columns = (
        "analysis_claim_token",
        "analysis_claimed_at",
        "analysis_claim_expires_at",
    )

    if is_postgres():
        for column_name in claim_columns:
            connection.execute(
                f"""
                ALTER TABLE candidate_job_analyses
                ADD COLUMN IF NOT EXISTS {column_name} TEXT
                """
            )

    else:
        existing_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(candidate_job_analyses)"
            ).fetchall()
        }

        for column_name in claim_columns:
            if column_name not in existing_columns:
                connection.execute(
                    f"""
                    ALTER TABLE candidate_job_analyses
                    ADD COLUMN {column_name} TEXT
                    """
                )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_candidate_job_analyses_claim_expiry
        ON candidate_job_analyses(
            candidate_id,
            analysis_claim_expires_at
        )
        """
    )


def _create_candidate_job_analysis_run_schema(
    connection,
) -> None:
    """
    Create immutable candidate-job analysis history.

    candidate_job_analyses remains the current-state
    projection.

    candidate_job_analysis_runs records how each analysis
    attempt was produced so reanalysis never destroys its
    previous provenance.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
        candidate_job_analysis_runs (
            id TEXT PRIMARY KEY,

            scan_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,

            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,

            run_mode TEXT NOT NULL
                CHECK (
                    run_mode IN (
                        'discovery',
                        'reanalysis'
                    )
                ),

            trigger_reasons_json TEXT
                NOT NULL DEFAULT '[]',

            analysis_version TEXT
                NOT NULL DEFAULT '',

            job_profile_version TEXT
                NOT NULL DEFAULT '',

            job_signature TEXT
                NOT NULL DEFAULT '',

            candidate_signature TEXT
                NOT NULL DEFAULT '',

            evidence_signature TEXT
                NOT NULL DEFAULT '',

            direction_signature TEXT
                NOT NULL DEFAULT '',

            constraint_signature TEXT
                NOT NULL DEFAULT '',

            career_memory_version INTEGER,

            career_memory_schema_version TEXT
                NOT NULL DEFAULT '',

            career_memory_source_signature TEXT
                NOT NULL DEFAULT '',

            career_memory_interpreted_source_signature TEXT
                NOT NULL DEFAULT '',

            result_state TEXT NOT NULL
                CHECK (
                    result_state IN (
                        'completed',
                        'failed'
                    )
                ),

            result_stage TEXT NOT NULL
                CHECK (
                    result_stage IN (
                        'preparation',
                        'hard_filter',
                        'batch_ai',
                        'persistence'
                    )
                ),

            analysis_json TEXT
                NOT NULL DEFAULT '{}',

            error_text TEXT
                NOT NULL DEFAULT '',

            created_at TEXT NOT NULL,

            UNIQUE (
                scan_id,
                batch_id,
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
        CREATE INDEX IF NOT EXISTS
        idx_candidate_job_analysis_runs_candidate_created
        ON candidate_job_analysis_runs(
            candidate_id,
            created_at
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_candidate_job_analysis_runs_job_created
        ON candidate_job_analysis_runs(
            candidate_id,
            job_id,
            created_at
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_candidate_job_analysis_runs_scan_batch
        ON candidate_job_analysis_runs(
            scan_id,
            batch_id
        )
        """
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

                analysis_state TEXT NOT NULL DEFAULT 'pending',
                opportunity_state TEXT NOT NULL DEFAULT 'none',

                status TEXT NOT NULL DEFAULT 'in_review',
                notes TEXT NOT NULL DEFAULT '',

                job_signature TEXT,

                evidence_signature TEXT,
                direction_signature TEXT,
                constraint_signature TEXT,

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

        # Sprint 8.5:
        # Add analysis/opportunity lifecycle columns only once.
        candidate_job_analysis_columns = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE
                table_schema = current_schema()
                AND table_name = 'candidate_job_analyses'
            """
        ).fetchall()

        candidate_job_analysis_column_names = {
            column["column_name"]
            for column in candidate_job_analysis_columns
        }

        for signature_column in (
            "evidence_signature",
            "direction_signature",
            "constraint_signature",
        ):
            if (
                signature_column
                not in candidate_job_analysis_column_names
            ):
                connection.execute(
                    f"""
                    ALTER TABLE candidate_job_analyses
                    ADD COLUMN {signature_column} TEXT
                    """
                )

        if (
            "analysis_state"
            not in candidate_job_analysis_column_names
        ):
            connection.execute(
                """
                ALTER TABLE candidate_job_analyses
                ADD COLUMN analysis_state TEXT
                NOT NULL DEFAULT 'pending'
                """
            )

            connection.execute(
                """
                UPDATE candidate_job_analyses
                SET analysis_state = CASE
                    WHEN status = 'in_review'
                         AND recommendation IS NULL
                        THEN 'pending'
                    ELSE 'analyzed'
                END
                """
            )

        if (
            "opportunity_state"
            not in candidate_job_analysis_column_names
        ):
            connection.execute(
                """
                ALTER TABLE candidate_job_analyses
                ADD COLUMN opportunity_state TEXT
                NOT NULL DEFAULT 'none'
                """
            )

            connection.execute(
                """
                UPDATE candidate_job_analyses
                SET opportunity_state = CASE
                    WHEN status = 'in_review'
                         AND recommendation IS NOT NULL
                        THEN 'active'

                    WHEN status IN (
                        'user_rejected',
                        'applied',
                        'in_process',
                        'rejected_before_interview',
                        'rejected_after_interview',
                        'offer'
                    )
                        THEN status

                    ELSE 'none'
                END
                """
            )

        _ensure_candidate_job_analysis_claim_columns(
            connection
        )

        _create_candidate_job_analysis_run_schema(
            connection
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
            CREATE TABLE IF NOT EXISTS job_discovery_signals (
                job_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT NOT NULL,
                search_query TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,

                PRIMARY KEY (
                    job_id,
                    source_type,
                    category,
                    sub_category,
                    search_query
                ),

                FOREIGN KEY (job_id)
                    REFERENCES jobs(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_job_discovery_signals_taxonomy
            ON job_discovery_signals(
                category,
                sub_category,
                job_id
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


        # ==================================================
        # Sprint 8.5 ? Career Memory Foundation
        # ==================================================

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            candidate_career_memory (
                candidate_id TEXT PRIMARY KEY,
                memory_version INTEGER NOT NULL,
                memory_schema_version TEXT NOT NULL,
                source_signature TEXT NOT NULL,
                interpreted_source_signature TEXT NOT NULL DEFAULT '',
                memory_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        # Existing PostgreSQL databases:
        # interpretation starts pending.
        connection.execute(
            """
            ALTER TABLE candidate_career_memory
            ADD COLUMN IF NOT EXISTS
                interpreted_source_signature
                TEXT NOT NULL DEFAULT ''
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            candidate_career_memory_events (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                event_type TEXT NOT NULL,

                authority TEXT NOT NULL
                    CHECK (
                        authority IN (
                            'fact',
                            'market_evidence',
                            'outcome',
                            'inference',
                            'hypothesis',
                            'continuity'
                        )
                    ),

                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL DEFAULT '',
                event_signature TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,

                UNIQUE (
                    candidate_id,
                    event_signature
                ),

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_career_memory_events_candidate_time
            ON candidate_career_memory_events(
                candidate_id,
                created_at
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_career_memory_events_authority
            ON candidate_career_memory_events(
                candidate_id,
                authority,
                created_at
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

                evidence_signature TEXT,
                direction_signature TEXT,
                constraint_signature TEXT,

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

        _ensure_candidate_job_analysis_claim_columns(
            connection
        )

        _create_candidate_job_analysis_run_schema(
            connection
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
            CREATE TABLE IF NOT EXISTS job_discovery_signals (
                job_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT NOT NULL,
                search_query TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,

                PRIMARY KEY (
                    job_id,
                    source_type,
                    category,
                    sub_category,
                    search_query
                ),

                FOREIGN KEY (job_id)
                    REFERENCES jobs(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_job_discovery_signals_taxonomy
            ON job_discovery_signals(
                category,
                sub_category,
                job_id
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

        candidate_job_analysis_columns = connection.execute(
            """
            PRAGMA table_info(candidate_job_analyses)
            """
        ).fetchall()

        candidate_job_analysis_column_names = {
            column["name"]
            for column in candidate_job_analysis_columns
        }

        for signature_column in (
            "evidence_signature",
            "direction_signature",
            "constraint_signature",
        ):
            if (
                signature_column
                not in candidate_job_analysis_column_names
            ):
                connection.execute(
                    f"""
                    ALTER TABLE candidate_job_analyses
                    ADD COLUMN {signature_column} TEXT
                    """
                )

        analysis_state_added = (
            "analysis_state"
            not in candidate_job_analysis_column_names
        )
        opportunity_state_added = (
            "opportunity_state"
            not in candidate_job_analysis_column_names
        )

        if analysis_state_added:
            connection.execute(
                """
                ALTER TABLE candidate_job_analyses
                ADD COLUMN analysis_state TEXT
                NOT NULL DEFAULT 'pending'
                """
            )

            connection.execute(
                """
                UPDATE candidate_job_analyses
                SET analysis_state = CASE
                    WHEN status = 'in_review'
                         AND recommendation IS NULL
                        THEN 'pending'
                    ELSE 'analyzed'
                END
                """
            )

        if opportunity_state_added:
            connection.execute(
                """
                ALTER TABLE candidate_job_analyses
                ADD COLUMN opportunity_state TEXT
                NOT NULL DEFAULT 'none'
                """
            )

            connection.execute(
                """
                UPDATE candidate_job_analyses
                SET opportunity_state = CASE
                    WHEN status = 'in_review'
                         AND recommendation IS NOT NULL
                        THEN 'active'

                    WHEN status IN (
                        'user_rejected',
                        'applied',
                        'in_process',
                        'rejected_before_interview',
                        'rejected_after_interview',
                        'offer'
                    )
                        THEN status

                    ELSE 'none'
                END
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


        # ==================================================
        # Sprint 8.5 ? Career Memory Foundation
        # ==================================================

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            candidate_career_memory (
                candidate_id TEXT PRIMARY KEY,
                memory_version INTEGER NOT NULL,
                memory_schema_version TEXT NOT NULL,
                source_signature TEXT NOT NULL,
                interpreted_source_signature TEXT NOT NULL DEFAULT '',
                memory_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        # Existing SQLite databases:
        # SQLite does not support ADD COLUMN IF NOT EXISTS
        # consistently across supported versions.
        career_memory_columns = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    candidate_career_memory
                )
                """
            ).fetchall()
        }

        if (
            "interpreted_source_signature"
            not in career_memory_columns
        ):
            connection.execute(
                """
                ALTER TABLE candidate_career_memory
                ADD COLUMN interpreted_source_signature
                    TEXT NOT NULL DEFAULT ''
                """
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            candidate_career_memory_events (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                event_type TEXT NOT NULL,

                authority TEXT NOT NULL
                    CHECK (
                        authority IN (
                            'fact',
                            'market_evidence',
                            'outcome',
                            'inference',
                            'hypothesis',
                            'continuity'
                        )
                    ),

                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL DEFAULT '',
                event_signature TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,

                UNIQUE (
                    candidate_id,
                    event_signature
                ),

                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_career_memory_events_candidate_time
            ON candidate_career_memory_events(
                candidate_id,
                created_at
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_career_memory_events_authority
            ON candidate_career_memory_events(
                candidate_id,
                authority,
                created_at
            )
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
                candidate_job_analyses.opportunity_state,
                candidate_job_analyses.created_at,
                candidate_job_analyses.updated_at,
                candidate_job_analyses.applied_at,
                candidate_job_analyses.rejected_at

            FROM candidate_job_analyses

            INNER JOIN jobs
                ON jobs.id =
                    candidate_job_analyses.job_id

            WHERE
                candidate_job_analyses.candidate_id = ?
                AND candidate_job_analyses.status = ?

                AND (
                    ? != 'in_review'

                    OR (
                        candidate_job_analyses.recommendation
                            IS NOT NULL

                        AND candidate_job_analyses.opportunity_state
                            = 'active'
                    )
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
                opportunity_state,
                COUNT(*) AS total

            FROM candidate_job_analyses

            WHERE candidate_id = ?

            GROUP BY
                status,
                opportunity_state
            """,
            (
                candidate_id,
            ),
        ).fetchall()

    for row in rows:
        status = row["status"]

        if status not in counts:
            continue

        # in_review is now the public/active
        # opportunity count.
        if (
            status == "in_review"
            and row["opportunity_state"]
            != "active"
        ):
            continue

        counts[status] += int(
            row["total"]
        )

    return counts


def list_inactive_approved_candidate_jobs(
    candidate_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Return worthwhile analyses that are ready to become
    opportunities but have not yet been activated.
    """
    if not candidate_id:
        raise ValueError(
            "Candidate ID is required."
        )

    if limit <= 0:
        raise ValueError(
            "Limit must be greater than zero."
        )

    approved = sorted(
        APPROVED_OPPORTUNITY_RECOMMENDATIONS
    )

    placeholders = ", ".join(
        "?"
        for _ in approved
    )

    query = f"""
        SELECT
            jobs.id,
            jobs.title,
            jobs.company,
            jobs.location,
            jobs.url,

            candidate_job_analyses.recommendation,
            candidate_job_analyses.current_fit,
            candidate_job_analyses.growth_value,
            candidate_job_analyses.analysis_json,
            candidate_job_analyses.updated_at

        FROM candidate_job_analyses

        INNER JOIN jobs
            ON jobs.id =
                candidate_job_analyses.job_id

        WHERE
            candidate_job_analyses.candidate_id = ?

            AND candidate_job_analyses.analysis_state
                = 'analyzed'

            AND candidate_job_analyses.opportunity_state
                = 'none'

            AND candidate_job_analyses.status
                = 'in_review'

            AND candidate_job_analyses.recommendation
                IN ({placeholders})

            AND jobs.archived_at IS NULL

        ORDER BY
            CASE candidate_job_analyses.recommendation
                WHEN 'best_match' THEN 0
                WHEN 'apply' THEN 0
                WHEN 'recommended_apply' THEN 0
                WHEN 'potential' THEN 1
                WHEN 'good_opportunity' THEN 2
                WHEN 'worth_second_look' THEN 2
                ELSE 3
            END,
            candidate_job_analyses.current_fit DESC,
            candidate_job_analyses.growth_value DESC,
            candidate_job_analyses.updated_at ASC

        LIMIT ?
    """

    params = [
        candidate_id,
        *approved,
        limit,
    ]

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(params),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def activate_candidate_opportunities(
    candidate_id: str,
    job_ids: list[str],
) -> list[str]:
    """
    Activate already-analyzed worthwhile jobs.

    Returns IDs actually activated in requested order.
    """
    if not candidate_id:
        raise ValueError(
            "Candidate ID is required."
        )

    normalized_job_ids = list(
        dict.fromkeys(
            str(job_id).strip()
            for job_id in job_ids
            if str(job_id).strip()
        )
    )

    if not normalized_job_ids:
        return []

    activated: list[str] = []

    with get_connection() as connection:
        for job_id in normalized_job_ids:
            row = connection.execute(
                """
                SELECT
                    recommendation,
                    analysis_state,
                    opportunity_state,
                    status

                FROM candidate_job_analyses

                WHERE
                    candidate_id = ?
                    AND job_id = ?
                """,
                (
                    candidate_id,
                    job_id,
                ),
            ).fetchone()

            if row is None:
                continue

            if row["analysis_state"] != "analyzed":
                continue

            if row["opportunity_state"] != "none":
                continue

            if row["status"] != "in_review":
                continue

            if (
                row["recommendation"]
                not in APPROVED_OPPORTUNITY_RECOMMENDATIONS
            ):
                continue

            cursor = connection.execute(
                """
                UPDATE candidate_job_analyses

                SET
                    opportunity_state = 'active',
                    updated_at = ?

                WHERE
                    candidate_id = ?
                    AND job_id = ?
                    AND opportunity_state = 'none'
                """,
                (
                    utc_now(),
                    candidate_id,
                    job_id,
                ),
            )

            if cursor.rowcount:
                activated.append(
                    job_id
                )

    return activated


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
        row = connection.execute(
            """
            SELECT recommendation
            FROM candidate_job_analyses
            WHERE
                candidate_id = ?
                AND job_id = ?
            """,
            (
                candidate_id,
                job_id,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                "Candidate-job relationship was not found: "
                f"{candidate_id} / {job_id}"
            )

        recommendation = row["recommendation"]

        if (
            status == "in_review"
            and recommendation is not None
        ):
            opportunity_state = "active"
        elif status in APPLICATION_STATUSES:
            opportunity_state = status
        elif status == "user_rejected":
            opportunity_state = "user_rejected"
        else:
            opportunity_state = "none"

        connection.execute(
            """
            UPDATE candidate_job_analyses
            SET
                status = ?,
                opportunity_state = ?,
                updated_at = ?,
                applied_at = COALESCE(?, applied_at),
                rejected_at = COALESCE(?, rejected_at)
            WHERE
                candidate_id = ?
                AND job_id = ?
            """,
            (
                status,
                opportunity_state,
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


def _claim_candidate_job_analysis_rows(
    *,
    candidate_id: str,
    rows: list[dict[str, Any]],
    claim_token: str,
    claim_ttl_seconds: int,
    run_mode: str,
    evidence_signature: str = "",
    direction_signature: str = "",
    constraint_signature: str = "",
) -> list[dict[str, Any]]:
    """
    Claim candidate-job analysis work using compare-and-set.

    The input rows may have been selected concurrently by
    multiple workers. Ownership is established only by the
    guarded UPDATE below.
    """
    normalized_candidate_id = str(
        candidate_id or ""
    ).strip()

    normalized_token = str(
        claim_token or ""
    ).strip()

    if not normalized_candidate_id:
        raise ValueError(
            "Candidate ID is required."
        )

    if not normalized_token:
        raise ValueError(
            "Analysis claim token is required."
        )

    if claim_ttl_seconds <= 0:
        raise ValueError(
            "Claim TTL must be greater than zero."
        )

    if run_mode not in {
        "discovery",
        "reanalysis",
    }:
        raise ValueError(
            f"Invalid claim run mode: {run_mode}"
        )

    now_dt = datetime.now(
        timezone.utc
    )

    claimed_at = now_dt.isoformat()

    claim_expires_at = (
        now_dt
        + timedelta(
            seconds=claim_ttl_seconds
        )
    ).isoformat()

    claimed_rows: list[
        dict[str, Any]
    ] = []

    with get_connection() as connection:
        for source_row in rows:
            job_id = str(
                source_row.get(
                    "id",
                    ""
                )
            ).strip()

            if not job_id:
                continue

            if run_mode == "discovery":
                eligibility_sql = """
                    AND analysis_state = 'pending'
                    AND opportunity_state = 'none'
                """

                eligibility_params: list[Any] = []

            else:
                eligibility_sql = """
                    AND analysis_state = 'analyzed'
                    AND status = 'in_review'
                    AND opportunity_state
                        IN ('none', 'active')

                    AND (
                        COALESCE(
                            evidence_signature,
                            ''
                        ) <> ?

                        OR COALESCE(
                            direction_signature,
                            ''
                        ) <> ?

                        OR COALESCE(
                            constraint_signature,
                            ''
                        ) <> ?
                    )
                """

                eligibility_params = [
                    str(
                        evidence_signature or ""
                    ),
                    str(
                        direction_signature or ""
                    ),
                    str(
                        constraint_signature or ""
                    ),
                ]

            cursor = connection.execute(
                f"""
                UPDATE candidate_job_analyses

                SET
                    analysis_claim_token = ?,
                    analysis_claimed_at = ?,
                    analysis_claim_expires_at = ?

                WHERE
                    candidate_id = ?
                    AND job_id = ?

                    {eligibility_sql}

                    AND (
                        COALESCE(
                            TRIM(
                                analysis_claim_token
                            ),
                            ''
                        ) = ''

                        OR analysis_claim_expires_at
                            IS NULL

                        OR analysis_claim_expires_at
                            <= ?

                        OR analysis_claim_token = ?
                    )
                """,
                (
                    normalized_token,
                    claimed_at,
                    claim_expires_at,
                    normalized_candidate_id,
                    job_id,
                    *eligibility_params,
                    claimed_at,
                    normalized_token,
                ),
            )

            if cursor.rowcount == 0:
                continue

            claimed_row = dict(
                source_row
            )

            claimed_row[
                "analysis_claim_token"
            ] = normalized_token

            claimed_row[
                "analysis_claimed_at"
            ] = claimed_at

            claimed_row[
                "analysis_claim_expires_at"
            ] = claim_expires_at

            claimed_rows.append(
                claimed_row
            )

    return claimed_rows


def release_candidate_job_analysis_claims(
    *,
    candidate_id: str,
    job_ids: list[str],
    claim_token: str,
) -> int:
    """
    Release only leases still owned by this token.

    An old worker therefore cannot clear a newer worker's
    claim.
    """
    normalized_candidate_id = str(
        candidate_id or ""
    ).strip()

    normalized_token = str(
        claim_token or ""
    ).strip()

    normalized_job_ids = list(
        dict.fromkeys(
            str(job_id).strip()
            for job_id in job_ids
            if str(job_id).strip()
        )
    )

    if (
        not normalized_candidate_id
        or not normalized_token
        or not normalized_job_ids
    ):
        return 0

    placeholders = ", ".join(
        "?"
        for _ in normalized_job_ids
    )

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE candidate_job_analyses

            SET
                analysis_claim_token = NULL,
                analysis_claimed_at = NULL,
                analysis_claim_expires_at = NULL

            WHERE
                candidate_id = ?
                AND job_id IN ({placeholders})
                AND analysis_claim_token = ?
            """,
            (
                normalized_candidate_id,
                *normalized_job_ids,
                normalized_token,
            ),
        )

        released = int(
            cursor.rowcount
        )

    return released


def list_pending_candidate_jobs(
    candidate_id: str,
    limit: int = 5,
    analysis_version: str | None = None,
    candidate_signature: str | None = None,
    job_ids: list[str] | None = None,
    claim_token: str | None = None,
    claim_ttl_seconds: int = 1800,
) -> list[dict[str, Any]]:
    """
    Return candidate-job relationships that have never
    completed their initial analysis.

    Sprint 8.5:
    Analysis/version/signature changes no longer make an
    analyzed job pending again. Reanalysis is a separate
    pipeline.

    analysis_version and candidate_signature remain as
    temporary compatibility parameters for legacy callers.
    """
    if not candidate_id:
        raise ValueError(
            "Candidate ID is required."
        )

    if limit <= 0:
        raise ValueError(
            "Limit must be greater than zero."
        )

    normalized_job_ids = None

    if job_ids is not None:
        normalized_job_ids = list(
            dict.fromkeys(
                str(job_id).strip()
                for job_id in job_ids
                if str(job_id).strip()
            )
        )

        if not normalized_job_ids:
            return []

    job_filter = ""
    claim_filter = ""

    params: list[Any] = [
        candidate_id,
    ]

    normalized_claim_token = str(
        claim_token or ""
    ).strip()

    if normalized_claim_token:
        claim_filter = """
            AND (
                COALESCE(
                    TRIM(
                        candidate_job_analyses
                        .analysis_claim_token
                    ),
                    ''
                ) = ''

                OR candidate_job_analyses
                    .analysis_claim_expires_at
                    IS NULL

                OR candidate_job_analyses
                    .analysis_claim_expires_at
                    <= ?

                OR candidate_job_analyses
                    .analysis_claim_token
                    = ?
            )
        """

        params.extend(
            [
                utc_now(),
                normalized_claim_token,
            ]
        )

    if normalized_job_ids is not None:
        placeholders = ", ".join(
            "?"
            for _ in normalized_job_ids
        )

        job_filter = (
            " AND candidate_job_analyses.job_id "
            f"IN ({placeholders})"
        )

        params.extend(
            normalized_job_ids
        )

    params.append(
        limit
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
                candidate_job_analyses.analysis_state,
                candidate_job_analyses.opportunity_state,
                candidate_job_analyses.status,
                candidate_job_analyses.created_at

            FROM candidate_job_analyses

            INNER JOIN jobs
                ON jobs.id =
                    candidate_job_analyses.job_id

            WHERE
                candidate_job_analyses.candidate_id = ?

                AND candidate_job_analyses.analysis_state = 'pending'

                AND candidate_job_analyses.opportunity_state = 'none'

                AND jobs.archived_at IS NULL

                {claim_filter}

                {job_filter}

            ORDER BY
                candidate_job_analyses.created_at ASC

            LIMIT ?
            """.format(
                claim_filter=claim_filter,
                job_filter=job_filter,
            ),
            tuple(params),
        ).fetchall()

    selected_rows = [
        dict(row)
        for row in rows
    ]

    if not normalized_claim_token:
        return selected_rows

    return _claim_candidate_job_analysis_rows(
        candidate_id=candidate_id,
        rows=selected_rows,
        claim_token=normalized_claim_token,
        claim_ttl_seconds=(
            claim_ttl_seconds
        ),
        run_mode="discovery",
    )



def _candidate_job_reanalysis_reasons(
    *,
    stored_evidence_signature: str | None,
    stored_direction_signature: str | None,
    stored_constraint_signature: str | None,
    current_evidence_signature: str,
    current_direction_signature: str,
    current_constraint_signature: str,
) -> list[str]:
    reasons: list[str] = []

    if (
        (stored_evidence_signature or "")
        != current_evidence_signature
    ):
        reasons.append(
            "evidence"
        )

    if (
        (stored_direction_signature or "")
        != current_direction_signature
    ):
        reasons.append(
            "direction"
        )

    if (
        (stored_constraint_signature or "")
        != current_constraint_signature
    ):
        reasons.append(
            "constraint"
        )

    return reasons


def list_candidate_jobs_for_reanalysis(
    *,
    candidate_id: str,
    evidence_signature: str,
    direction_signature: str,
    constraint_signature: str,
    limit: int = 50,
    job_ids: list[str] | None = None,
    claim_token: str | None = None,
    claim_ttl_seconds: int = 1800,
) -> list[dict[str, Any]]:
    """
    Return already-analyzed candidate jobs whose stored
    candidate-state signatures no longer match the current
    candidate state.

    Reanalysis is deliberately separate from discovery.

    Only live evaluation relationships are eligible:
    - analyzed
    - still in_review
    - opportunity_state none or active
    - job not archived

    Application/outcome lifecycle states are historical and
    are not silently rewritten by candidate-state changes.
    """
    normalized_candidate_id = str(
        candidate_id or ""
    ).strip()

    if not normalized_candidate_id:
        raise ValueError(
            "Candidate ID is required."
        )

    if limit <= 0:
        raise ValueError(
            "Limit must be greater than zero."
        )

    current_evidence_signature = str(
        evidence_signature or ""
    )

    current_direction_signature = str(
        direction_signature or ""
    )

    current_constraint_signature = str(
        constraint_signature or ""
    )

    normalized_job_ids = None

    if job_ids is not None:
        normalized_job_ids = list(
            dict.fromkeys(
                str(job_id).strip()
                for job_id in job_ids
                if str(job_id).strip()
            )
        )

        if not normalized_job_ids:
            return []

    job_filter = ""
    claim_filter = ""

    params: list[Any] = [
        normalized_candidate_id,
        current_evidence_signature,
        current_direction_signature,
        current_constraint_signature,
    ]

    normalized_claim_token = str(
        claim_token or ""
    ).strip()

    if normalized_claim_token:
        claim_filter = """
            AND (
                COALESCE(
                    TRIM(
                        candidate_job_analyses
                        .analysis_claim_token
                    ),
                    ''
                ) = ''

                OR candidate_job_analyses
                    .analysis_claim_expires_at
                    IS NULL

                OR candidate_job_analyses
                    .analysis_claim_expires_at
                    <= ?

                OR candidate_job_analyses
                    .analysis_claim_token
                    = ?
            )
        """

        params.extend(
            [
                utc_now(),
                normalized_claim_token,
            ]
        )

    if normalized_job_ids is not None:
        placeholders = ", ".join(
            "?"
            for _ in normalized_job_ids
        )

        job_filter = (
            " AND candidate_job_analyses.job_id "
            f"IN ({placeholders})"
        )

        params.extend(
            normalized_job_ids
        )

    params.append(
        limit
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

                candidate_job_analyses.evidence_signature,
                candidate_job_analyses.direction_signature,
                candidate_job_analyses.constraint_signature,

                candidate_job_analyses.recommendation,
                candidate_job_analyses.analysis_state,
                candidate_job_analyses.opportunity_state,
                candidate_job_analyses.status,
                candidate_job_analyses.created_at,
                candidate_job_analyses.updated_at

            FROM candidate_job_analyses

            INNER JOIN jobs
                ON jobs.id =
                    candidate_job_analyses.job_id

            WHERE
                candidate_job_analyses.candidate_id = ?

                AND candidate_job_analyses.analysis_state
                    = 'analyzed'

                AND candidate_job_analyses.status
                    = 'in_review'

                AND candidate_job_analyses.opportunity_state
                    IN ('none', 'active')

                AND jobs.archived_at IS NULL

                AND (
                    COALESCE(
                        candidate_job_analyses.evidence_signature,
                        ''
                    ) <> ?

                    OR COALESCE(
                        candidate_job_analyses.direction_signature,
                        ''
                    ) <> ?

                    OR COALESCE(
                        candidate_job_analyses.constraint_signature,
                        ''
                    ) <> ?
                )

                {claim_filter}

                {job_filter}

            ORDER BY
                candidate_job_analyses.updated_at ASC,
                candidate_job_analyses.created_at ASC

            LIMIT ?
            """.format(
                claim_filter=claim_filter,
                job_filter=job_filter,
            ),
            tuple(params),
        ).fetchall()

    selected_rows = [
        dict(row)
        for row in rows
    ]

    if normalized_claim_token:
        selected_rows = (
            _claim_candidate_job_analysis_rows(
                candidate_id=(
                    normalized_candidate_id
                ),
                rows=selected_rows,
                claim_token=(
                    normalized_claim_token
                ),
                claim_ttl_seconds=(
                    claim_ttl_seconds
                ),
                run_mode="reanalysis",
                evidence_signature=(
                    current_evidence_signature
                ),
                direction_signature=(
                    current_direction_signature
                ),
                constraint_signature=(
                    current_constraint_signature
                ),
            )
        )

    result: list[
        dict[str, Any]
    ] = []

    for item in selected_rows:

        reasons = (
            _candidate_job_reanalysis_reasons(
                stored_evidence_signature=(
                    item.get(
                        "evidence_signature"
                    )
                ),
                stored_direction_signature=(
                    item.get(
                        "direction_signature"
                    )
                ),
                stored_constraint_signature=(
                    item.get(
                        "constraint_signature"
                    )
                ),
                current_evidence_signature=(
                    current_evidence_signature
                ),
                current_direction_signature=(
                    current_direction_signature
                ),
                current_constraint_signature=(
                    current_constraint_signature
                ),
            )
        )

        # SQL already guarantees at least one mismatch.
        # Keep this guard so the Python contract remains
        # correct even if the query changes later.
        if not reasons:
            continue

        item[
            "reanalysis_reasons"
        ] = reasons

        result.append(
            item
        )

    return result


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


def _save_candidate_job_analysis_on_connection(
    connection,
    *,
    candidate_id: str,
    job_id: str,
    analysis: dict[str, Any],
    job_signature: str,
    candidate_signature: str,
    analysis_version: str,
    status: str = "in_review",
    evidence_signature: str | None = None,
    direction_signature: str | None = None,
    constraint_signature: str | None = None,
    opportunity_state: str | None = None,
    analysis_claim_token: str | None = None,
) -> None:
    """
    Persist the current candidate-job analysis using an
    existing transaction.

    Keeping this operation connection-scoped allows the
    current-state projection and immutable history record
    to commit or roll back together.
    """
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

    # Analysis completion and opportunity lifecycle
    # are independent dimensions.
    analysis_state = "analyzed"

    if opportunity_state is not None:
        if (
            opportunity_state
            not in VALID_OPPORTUNITY_STATES
        ):
            raise ValueError(
                "Invalid opportunity_state: "
                f"{opportunity_state}"
            )

        resolved_opportunity_state = (
            opportunity_state
        )

    elif (
        status == "in_review"
        and recommendation is not None
    ):
        # Legacy compatibility for callers that have
        # not yet migrated to explicit activation.
        resolved_opportunity_state = "active"

    elif status in APPLICATION_STATUSES:
        resolved_opportunity_state = status

    elif status == "user_rejected":
        resolved_opportunity_state = (
            "user_rejected"
        )

    else:
        resolved_opportunity_state = "none"

    rejected_at = (
        now
        if status == "rejected"
        else None
    )

    normalized_claim_token = str(
        analysis_claim_token or ""
    ).strip()

    claim_clear_sql = ""
    claim_guard_sql = ""
    claim_guard_params: list[Any] = []

    if normalized_claim_token:
        claim_clear_sql = """
            ,
            analysis_claim_token = NULL,
            analysis_claimed_at = NULL,
            analysis_claim_expires_at = NULL
        """

        claim_guard_sql = """
            AND analysis_claim_token = ?
            AND analysis_claim_expires_at IS NOT NULL
            AND analysis_claim_expires_at > ?
        """

        claim_guard_params = [
            normalized_claim_token,
            now,
        ]

    cursor = connection.execute(
        f"""
        UPDATE candidate_job_analyses

        SET
            recommendation = ?,
            competitive_status = ?,
            current_fit = ?,
            growth_value = ?,
            analysis_json = ?,
            job_signature = ?,
            candidate_signature = ?,
            evidence_signature = ?,
            direction_signature = ?,
            constraint_signature = ?,
            analysis_version = ?,
            analysis_state = ?,
            opportunity_state = ?,
            status = ?,
            rejected_at = ?,
            updated_at = ?

            {claim_clear_sql}

        WHERE
            candidate_id = ?
            AND job_id = ?

            {claim_guard_sql}
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
            evidence_signature,
            direction_signature,
            constraint_signature,
            analysis_version,
            analysis_state,
            resolved_opportunity_state,
            status,
            rejected_at,
            now,
            candidate_id,
            job_id,
            *claim_guard_params,
        ),
    )

    if cursor.rowcount == 0:
        if normalized_claim_token:
            raise CandidateJobAnalysisClaimLostError(
                "Candidate-job analysis claim was lost "
                "before persistence: "
                f"{candidate_id} / {job_id}"
            )

        raise ValueError(
            "Candidate-job relationship was not found: "
            f"{candidate_id} / {job_id}"
        )


def _append_candidate_job_analysis_run_on_connection(
    connection,
    *,
    scan_id: str,
    batch_id: str,
    candidate_id: str,
    job_id: str,
    run_mode: str,
    trigger_reasons: list[str],
    analysis_version: str,
    job_profile_version: str,
    job_signature: str,
    candidate_signature: str,
    evidence_signature: str,
    direction_signature: str,
    constraint_signature: str,
    career_memory_version: int | None,
    career_memory_schema_version: str,
    career_memory_source_signature: str,
    career_memory_interpreted_source_signature: str,
    result_state: str,
    result_stage: str,
    analysis: dict[str, Any] | None = None,
    error_text: str = "",
) -> None:
    """
    Append one immutable analysis execution record.

    No ON CONFLICT update is allowed here. A duplicate
    scan/batch/candidate/job tuple is a traceability
    violation and must fail rather than rewrite history.
    """
    normalized_reasons = []

    for reason in trigger_reasons:
        normalized = str(
            reason or ""
        ).strip()

        if (
            normalized
            and normalized
            not in normalized_reasons
        ):
            normalized_reasons.append(
                normalized
            )

    connection.execute(
        """
        INSERT INTO candidate_job_analysis_runs (
            id,
            scan_id,
            batch_id,
            candidate_id,
            job_id,
            run_mode,
            trigger_reasons_json,
            analysis_version,
            job_profile_version,
            job_signature,
            candidate_signature,
            evidence_signature,
            direction_signature,
            constraint_signature,
            career_memory_version,
            career_memory_schema_version,
            career_memory_source_signature,
            career_memory_interpreted_source_signature,
            result_state,
            result_stage,
            analysis_json,
            error_text,
            created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            (
                "candidate_job_analysis_run_"
                + uuid4().hex
            ),
            str(scan_id or "").strip(),
            str(batch_id or "").strip(),
            str(candidate_id or "").strip(),
            str(job_id or "").strip(),
            str(run_mode or "").strip(),
            json.dumps(
                normalized_reasons,
                ensure_ascii=False,
            ),
            str(
                analysis_version or ""
            ).strip(),
            str(
                job_profile_version or ""
            ).strip(),
            str(
                job_signature or ""
            ).strip(),
            str(
                candidate_signature or ""
            ).strip(),
            str(
                evidence_signature or ""
            ).strip(),
            str(
                direction_signature or ""
            ).strip(),
            str(
                constraint_signature or ""
            ).strip(),
            career_memory_version,
            str(
                career_memory_schema_version
                or ""
            ).strip(),
            str(
                career_memory_source_signature
                or ""
            ).strip(),
            str(
                career_memory_interpreted_source_signature
                or ""
            ).strip(),
            str(
                result_state or ""
            ).strip(),
            str(
                result_stage or ""
            ).strip(),
            json.dumps(
                analysis or {},
                ensure_ascii=False,
            ),
            str(
                error_text or ""
            ),
            utc_now(),
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
    evidence_signature: str | None = None,
    direction_signature: str | None = None,
    constraint_signature: str | None = None,
    opportunity_state: str | None = None,
) -> None:
    """
    Legacy/current-state persistence API.

    Existing callers keep exactly the same behavior.
    """
    with get_connection() as connection:
        _save_candidate_job_analysis_on_connection(
            connection,
            candidate_id=candidate_id,
            job_id=job_id,
            analysis=analysis,
            job_signature=job_signature,
            candidate_signature=(
                candidate_signature
            ),
            analysis_version=analysis_version,
            status=status,
            evidence_signature=evidence_signature,
            direction_signature=direction_signature,
            constraint_signature=constraint_signature,
            opportunity_state=opportunity_state,
        )


def save_candidate_job_analysis_with_run(
    *,
    candidate_id: str,
    job_id: str,
    analysis: dict[str, Any],
    job_signature: str,
    candidate_signature: str,
    analysis_version: str,
    status: str,
    opportunity_state: str,
    evidence_signature: str,
    direction_signature: str,
    constraint_signature: str,
    scan_id: str,
    batch_id: str,
    run_mode: str,
    trigger_reasons: list[str],
    job_profile_version: str,
    career_memory_version: int | None,
    career_memory_schema_version: str,
    career_memory_source_signature: str,
    career_memory_interpreted_source_signature: str,
    result_stage: str,
    analysis_claim_token: str | None = None,
) -> None:
    """
    Atomically update current state and append its
    immutable provenance record.

    Either both persist or neither persists.
    """
    with get_connection() as connection:
        _save_candidate_job_analysis_on_connection(
            connection,
            candidate_id=candidate_id,
            job_id=job_id,
            analysis=analysis,
            job_signature=job_signature,
            candidate_signature=(
                candidate_signature
            ),
            analysis_version=analysis_version,
            status=status,
            evidence_signature=evidence_signature,
            direction_signature=direction_signature,
            constraint_signature=constraint_signature,
            opportunity_state=opportunity_state,
            analysis_claim_token=(
                analysis_claim_token
            ),
        )

        _append_candidate_job_analysis_run_on_connection(
            connection,
            scan_id=scan_id,
            batch_id=batch_id,
            candidate_id=candidate_id,
            job_id=job_id,
            run_mode=run_mode,
            trigger_reasons=trigger_reasons,
            analysis_version=analysis_version,
            job_profile_version=job_profile_version,
            job_signature=job_signature,
            candidate_signature=(
                candidate_signature
            ),
            evidence_signature=evidence_signature,
            direction_signature=direction_signature,
            constraint_signature=constraint_signature,
            career_memory_version=(
                career_memory_version
            ),
            career_memory_schema_version=(
                career_memory_schema_version
            ),
            career_memory_source_signature=(
                career_memory_source_signature
            ),
            career_memory_interpreted_source_signature=(
                career_memory_interpreted_source_signature
            ),
            result_state="completed",
            result_stage=result_stage,
            analysis=analysis,
            error_text="",
        )


def append_candidate_job_analysis_run(
    *,
    scan_id: str,
    batch_id: str,
    candidate_id: str,
    job_id: str,
    run_mode: str,
    trigger_reasons: list[str],
    analysis_version: str,
    job_profile_version: str,
    job_signature: str,
    candidate_signature: str,
    evidence_signature: str,
    direction_signature: str,
    constraint_signature: str,
    career_memory_version: int | None,
    career_memory_schema_version: str,
    career_memory_source_signature: str,
    career_memory_interpreted_source_signature: str,
    result_state: str,
    result_stage: str,
    analysis: dict[str, Any] | None = None,
    error_text: str = "",
) -> None:
    """
    Append traceability when no current-state write
    belongs in the same transaction, such as preparation
    or batch-AI failure.
    """
    with get_connection() as connection:
        _append_candidate_job_analysis_run_on_connection(
            connection,
            scan_id=scan_id,
            batch_id=batch_id,
            candidate_id=candidate_id,
            job_id=job_id,
            run_mode=run_mode,
            trigger_reasons=trigger_reasons,
            analysis_version=analysis_version,
            job_profile_version=job_profile_version,
            job_signature=job_signature,
            candidate_signature=(
                candidate_signature
            ),
            evidence_signature=evidence_signature,
            direction_signature=direction_signature,
            constraint_signature=constraint_signature,
            career_memory_version=(
                career_memory_version
            ),
            career_memory_schema_version=(
                career_memory_schema_version
            ),
            career_memory_source_signature=(
                career_memory_source_signature
            ),
            career_memory_interpreted_source_signature=(
                career_memory_interpreted_source_signature
            ),
            result_state=result_state,
            result_stage=result_stage,
            analysis=analysis,
            error_text=error_text,
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
