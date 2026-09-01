import json
import sqlite3

import pytest

import services.database as database

from services.database import (
    _create_candidate_job_analysis_run_schema,
    append_candidate_job_analysis_run,
    save_candidate_job_analysis,
    save_candidate_job_analysis_with_run,
)


def _prepare_database(
    tmp_path,
    monkeypatch,
):
    database_file = (
        tmp_path
        / "atomic-analysis.db"
    )

    monkeypatch.delenv(
        "DATABASE_URL",
        raising=False,
    )

    monkeypatch.setattr(
        database,
        "DATABASE_FILE",
        database_file,
    )

    connection = sqlite3.connect(
        database_file
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

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

    connection.execute(
        """
        CREATE TABLE candidate_job_analyses (
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,

            recommendation TEXT,
            competitive_status TEXT,
            current_fit INTEGER,
            growth_value INTEGER,

            analysis_json TEXT NOT NULL
                DEFAULT '{}',

            analysis_state TEXT NOT NULL
                DEFAULT 'pending',

            opportunity_state TEXT NOT NULL
                DEFAULT 'none',

            status TEXT NOT NULL
                DEFAULT 'in_review',

            notes TEXT NOT NULL
                DEFAULT '',

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

    _create_candidate_job_analysis_run_schema(
        connection
    )

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

    connection.execute(
        """
        INSERT INTO candidate_job_analyses (
            candidate_id,
            job_id,
            analysis_json,
            analysis_state,
            opportunity_state,
            status,
            notes,
            created_at,
            updated_at
        )
        VALUES (
            'candidate-1',
            'job-1',
            '{}',
            'pending',
            'none',
            'in_review',
            '',
            'before',
            'before'
        )
        """
    )

    connection.commit()
    connection.close()

    return database_file


def _atomic_kwargs(
    analysis,
):
    return {
        "candidate_id": "candidate-1",
        "job_id": "job-1",
        "analysis": analysis,
        "job_signature": "job-signature",
        "candidate_signature": (
            "candidate-signature"
        ),
        "analysis_version": (
            "candidate-job-analysis-v15"
        ),
        "status": "in_review",
        "opportunity_state": "none",
        "evidence_signature": "e-v1",
        "direction_signature": "d-v1",
        "constraint_signature": "c-v1",
        "scan_id": "scan-1",
        "batch_id": "batch-1",
        "run_mode": "discovery",
        "trigger_reasons": [
            "initial_analysis",
        ],
        "job_profile_version": (
            "job-profile-v2"
        ),
        "career_memory_version": 3,
        "career_memory_schema_version": (
            "career-memory-v1"
        ),
        "career_memory_source_signature": (
            "memory-source"
        ),
        (
            "career_memory_"
            "interpreted_source_signature"
        ): "memory-source",
        "result_stage": "batch_ai",
    }


def test_current_state_and_run_commit_together(
    tmp_path,
    monkeypatch,
):
    database_file = _prepare_database(
        tmp_path,
        monkeypatch,
    )

    analysis = {
        "recommendation": "best_match",
        "competitive_status": "strong",
        "current_fit": 88,
        "growth_value": 70,
    }

    save_candidate_job_analysis_with_run(
        **_atomic_kwargs(
            analysis
        )
    )

    connection = sqlite3.connect(
        database_file
    )

    connection.row_factory = sqlite3.Row

    try:
        current = connection.execute(
            """
            SELECT *
            FROM candidate_job_analyses
            WHERE
                candidate_id = 'candidate-1'
                AND job_id = 'job-1'
            """
        ).fetchone()

        runs = connection.execute(
            """
            SELECT *
            FROM candidate_job_analysis_runs
            """
        ).fetchall()

        assert (
            current["recommendation"]
            == "best_match"
        )

        assert (
            current["analysis_state"]
            == "analyzed"
        )

        assert len(runs) == 1

        assert runs[0]["scan_id"] == "scan-1"
        assert runs[0]["batch_id"] == "batch-1"

        assert (
            runs[0]["result_state"]
            == "completed"
        )

        assert (
            json.loads(
                runs[0]["analysis_json"]
            )["recommendation"]
            == "best_match"
        )

    finally:
        connection.close()


def test_duplicate_run_rolls_back_current_state_update(
    tmp_path,
    monkeypatch,
):
    database_file = _prepare_database(
        tmp_path,
        monkeypatch,
    )

    first_analysis = {
        "recommendation": "best_match",
        "competitive_status": "strong",
        "current_fit": 90,
        "growth_value": 60,
    }

    save_candidate_job_analysis_with_run(
        **_atomic_kwargs(
            first_analysis
        )
    )

    second_analysis = {
        "recommendation": "reject",
        "competitive_status": (
            "not_competitive_now"
        ),
        "current_fit": 10,
        "growth_value": 5,
    }

    # Same scan/batch/candidate/job tuple violates
    # immutable history uniqueness. Because the current
    # UPDATE and run INSERT share one transaction, the
    # attempted current-state rewrite must roll back too.
    with pytest.raises(
        sqlite3.IntegrityError
    ):
        save_candidate_job_analysis_with_run(
            **_atomic_kwargs(
                second_analysis
            )
        )

    connection = sqlite3.connect(
        database_file
    )

    connection.row_factory = sqlite3.Row

    try:
        current = connection.execute(
            """
            SELECT
                recommendation,
                current_fit,
                analysis_json
            FROM candidate_job_analyses
            WHERE
                candidate_id = 'candidate-1'
                AND job_id = 'job-1'
            """
        ).fetchone()

        run_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM candidate_job_analysis_runs
            """
        ).fetchone()["total"]

        assert (
            current["recommendation"]
            == "best_match"
        )

        assert current["current_fit"] == 90

        assert (
            json.loads(
                current["analysis_json"]
            )["recommendation"]
            == "best_match"
        )

        assert run_count == 1

    finally:
        connection.close()


def test_legacy_save_and_standalone_failure_run_remain_separate(
    tmp_path,
    monkeypatch,
):
    database_file = _prepare_database(
        tmp_path,
        monkeypatch,
    )

    save_candidate_job_analysis(
        candidate_id="candidate-1",
        job_id="job-1",
        analysis={
            "recommendation": "potential",
            "current_fit": 70,
            "growth_value": 80,
        },
        job_signature="job-signature",
        candidate_signature=(
            "candidate-signature"
        ),
        evidence_signature="e-v1",
        direction_signature="d-v1",
        constraint_signature="c-v1",
        analysis_version=(
            "candidate-job-analysis-v15"
        ),
        status="in_review",
        opportunity_state="none",
    )

    append_candidate_job_analysis_run(
        scan_id="scan-failure",
        batch_id="batch-failure",
        candidate_id="candidate-1",
        job_id="job-1",
        run_mode="discovery",
        trigger_reasons=[
            "initial_analysis",
        ],
        analysis_version=(
            "candidate-job-analysis-v15"
        ),
        job_profile_version=(
            "job-profile-v2"
        ),
        job_signature="job-signature",
        candidate_signature=(
            "candidate-signature"
        ),
        evidence_signature="e-v1",
        direction_signature="d-v1",
        constraint_signature="c-v1",
        career_memory_version=None,
        career_memory_schema_version="",
        career_memory_source_signature="",
        career_memory_interpreted_source_signature="",
        result_state="failed",
        result_stage="batch_ai",
        analysis=None,
        error_text="provider failure",
    )

    connection = sqlite3.connect(
        database_file
    )

    connection.row_factory = sqlite3.Row

    try:
        run = connection.execute(
            """
            SELECT *
            FROM candidate_job_analysis_runs
            """
        ).fetchone()

        assert run is not None

        assert run["result_state"] == "failed"
        assert run["result_stage"] == "batch_ai"

        assert (
            run["error_text"]
            == "provider failure"
        )

        current = connection.execute(
            """
            SELECT recommendation
            FROM candidate_job_analyses
            WHERE
                candidate_id = 'candidate-1'
                AND job_id = 'job-1'
            """
        ).fetchone()

        assert (
            current["recommendation"]
            == "potential"
        )

    finally:
        connection.close()
