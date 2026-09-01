import sqlite3

import pytest

from services.database import (
    _create_candidate_job_analysis_run_schema,
    get_connection,
    is_postgres,
)


EXPECTED_COLUMNS = {
    "id",
    "scan_id",
    "batch_id",
    "candidate_id",
    "job_id",
    "run_mode",
    "trigger_reasons_json",
    "analysis_version",
    "job_profile_version",
    "job_signature",
    "candidate_signature",
    "evidence_signature",
    "direction_signature",
    "constraint_signature",
    "career_memory_version",
    "career_memory_schema_version",
    "career_memory_source_signature",
    "career_memory_interpreted_source_signature",
    "result_state",
    "result_stage",
    "analysis_json",
    "error_text",
    "created_at",
}


EXPECTED_INDEXES = {
    (
        "idx_candidate_job_analysis_runs_"
        "candidate_created"
    ),
    (
        "idx_candidate_job_analysis_runs_"
        "job_created"
    ),
    (
        "idx_candidate_job_analysis_runs_"
        "scan_batch"
    ),
}


def _create_sqlite_parent_tables(
    connection,
):
    connection.execute(
        """
        CREATE TABLE candidates (
            id TEXT PRIMARY KEY
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY
        )
        """
    )


def _valid_run_values():
    return (
        "run-1",
        "scan-1",
        "batch-1",
        "candidate-1",
        "job-1",
        "discovery",
        '["initial_analysis"]',
        "candidate-analysis-v1",
        "job-profile-v2",
        "job-signature",
        "candidate-signature",
        "evidence-signature",
        "direction-signature",
        "constraint-signature",
        1,
        "career-memory-v1",
        "memory-source",
        "memory-source",
        "completed",
        "batch_ai",
        '{"recommendation":"best_match"}',
        "",
        "2026-09-01T08:00:00+00:00",
    )


INSERT_SQL = """
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
"""


def test_sqlite_analysis_run_schema_and_constraints():
    connection = sqlite3.connect(
        ":memory:"
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:
        _create_sqlite_parent_tables(
            connection
        )

        _create_candidate_job_analysis_run_schema(
            connection
        )

        columns = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    candidate_job_analysis_runs
                )
                """
            ).fetchall()
        }

        assert EXPECTED_COLUMNS <= columns

        indexes = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA index_list(
                    candidate_job_analysis_runs
                )
                """
            ).fetchall()
        }

        assert EXPECTED_INDEXES <= indexes

        connection.execute(
            """
            INSERT INTO candidates (id)
            VALUES ('candidate-1')
            """
        )

        connection.execute(
            """
            INSERT INTO jobs (id)
            VALUES ('job-1')
            """
        )

        values = _valid_run_values()

        connection.execute(
            INSERT_SQL,
            values,
        )

        # Same scan/batch/candidate/job tuple is
        # intentionally idempotency-protected.
        duplicate = list(values)
        duplicate[0] = "run-2"

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                INSERT_SQL,
                duplicate,
            )

        invalid_mode = list(values)
        invalid_mode[0] = "run-3"
        invalid_mode[1] = "scan-2"
        invalid_mode[5] = "invalid-mode"

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                INSERT_SQL,
                invalid_mode,
            )

        invalid_state = list(values)
        invalid_state[0] = "run-4"
        invalid_state[1] = "scan-3"
        invalid_state[18] = "unknown"

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                INSERT_SQL,
                invalid_state,
            )

    finally:
        connection.close()


def test_postgres_analysis_run_schema_is_present():
    if not is_postgres():
        pytest.skip(
            "PostgreSQL is not configured."
        )

    # Also makes the migration retry-safe when
    # this test is run against an existing DB.
    with get_connection() as connection:
        _create_candidate_job_analysis_run_schema(
            connection
        )

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE
                table_schema = current_schema()
                AND table_name =
                    'candidate_job_analysis_runs'
            """
        ).fetchall()

        columns = {
            row["column_name"]
            for row in rows
        }

        assert EXPECTED_COLUMNS <= columns

        index_rows = connection.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE
                schemaname = current_schema()
                AND tablename =
                    'candidate_job_analysis_runs'
            """
        ).fetchall()

        indexes = {
            row["indexname"]
            for row in index_rows
        }

        assert EXPECTED_INDEXES <= indexes


def test_traceability_schema_creation_is_retry_safe():
    if not is_postgres():
        pytest.skip(
            "PostgreSQL is not configured."
        )

    with get_connection() as connection:
        _create_candidate_job_analysis_run_schema(
            connection
        )

        _create_candidate_job_analysis_run_schema(
            connection
        )

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM information_schema.tables
            WHERE
                table_schema = current_schema()
                AND table_name =
                    'candidate_job_analysis_runs'
            """
        ).fetchone()

    assert int(row["total"]) == 1
