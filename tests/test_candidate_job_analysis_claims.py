import sqlite3

import pytest

import services.database as database


def _prepare_database(
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv(
        "DATABASE_URL",
        raising=False,
    )

    database_file = (
        tmp_path
        / "candidate-job-claims.db"
    )

    monkeypatch.setattr(
        database,
        "DATABASE_FILE",
        database_file,
    )

    connection = sqlite3.connect(
        database_file
    )

    try:
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
                id TEXT PRIMARY KEY,
                raw_text TEXT NOT NULL DEFAULT '',
                url TEXT,
                title TEXT,
                company TEXT,
                location TEXT,
                remote INTEGER,
                salary TEXT,
                easy_apply INTEGER,
                description TEXT,
                archived_at TEXT
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

                analysis_json TEXT NOT NULL DEFAULT '{}',

                analysis_state TEXT NOT NULL
                    DEFAULT 'pending',

                opportunity_state TEXT NOT NULL
                    DEFAULT 'none',

                status TEXT NOT NULL
                    DEFAULT 'in_review',

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
                )
            )
            """
        )

        database._ensure_candidate_job_analysis_claim_columns(
            connection
        )

        database._create_candidate_job_analysis_run_schema(
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
            INSERT INTO jobs (
                id,
                raw_text,
                title,
                company,
                location,
                description
            )
            VALUES (
                'job-1',
                '',
                'Support Engineer',
                'Example',
                'Ireland',
                'Example job'
            )
            """
        )

        now = database.utc_now()

        connection.execute(
            """
            INSERT INTO candidate_job_analyses (
                candidate_id,
                job_id,
                analysis_state,
                opportunity_state,
                status,
                created_at,
                updated_at
            )
            VALUES (
                'candidate-1',
                'job-1',
                'pending',
                'none',
                'in_review',
                ?,
                ?
            )
            """,
            (
                now,
                now,
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return database_file


def test_only_one_active_discovery_claim_wins(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    first = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-a",
            claim_ttl_seconds=600,
        )
    )

    second = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-b",
            claim_ttl_seconds=600,
        )
    )

    assert len(first) == 1
    assert first[0][
        "analysis_claim_token"
    ] == "claim-a"

    assert second == []


def test_released_claim_can_be_acquired_again(
    monkeypatch,
    tmp_path,
):
    _prepare_database(
        monkeypatch,
        tmp_path,
    )

    first = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-a",
            claim_ttl_seconds=600,
        )
    )

    assert len(first) == 1

    released = (
        database.release_candidate_job_analysis_claims(
            candidate_id="candidate-1",
            job_ids=["job-1"],
            claim_token="claim-a",
        )
    )

    assert released == 1

    second = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-b",
            claim_ttl_seconds=600,
        )
    )

    assert len(second) == 1
    assert second[0][
        "analysis_claim_token"
    ] == "claim-b"


def test_expired_claim_can_be_recovered(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    first = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-a",
            claim_ttl_seconds=600,
        )
    )

    assert len(first) == 1

    connection = sqlite3.connect(
        database_file
    )

    try:
        connection.execute(
            """
            UPDATE candidate_job_analyses
            SET analysis_claim_expires_at =
                '2000-01-01T00:00:00+00:00'
            WHERE
                candidate_id = 'candidate-1'
                AND job_id = 'job-1'
            """
        )

        connection.commit()

    finally:
        connection.close()

    second = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-b",
            claim_ttl_seconds=600,
        )
    )

    assert len(second) == 1
    assert second[0][
        "analysis_claim_token"
    ] == "claim-b"


def test_stale_owner_cannot_persist_over_new_owner(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    first = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-a",
            claim_ttl_seconds=600,
        )
    )

    assert len(first) == 1

    connection = sqlite3.connect(
        database_file
    )

    try:
        connection.execute(
            """
            UPDATE candidate_job_analyses
            SET analysis_claim_expires_at =
                '2000-01-01T00:00:00+00:00'
            WHERE
                candidate_id = 'candidate-1'
                AND job_id = 'job-1'
            """
        )

        connection.commit()

    finally:
        connection.close()

    second = (
        database.list_pending_candidate_jobs(
            candidate_id="candidate-1",
            limit=1,
            claim_token="claim-b",
            claim_ttl_seconds=600,
        )
    )

    assert len(second) == 1

    analysis = {
        "recommendation": "potential",
        "competitive_status": "potential",
        "current_fit": 70,
        "growth_value": 80,
    }

    common = {
        "candidate_id": "candidate-1",
        "job_id": "job-1",
        "analysis": analysis,
        "job_signature": "job-v1",
        "candidate_signature": "candidate-v1",
        "analysis_version": "analysis-v1",
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
        "job_profile_version": "job-profile-v2",
        "career_memory_version": 1,
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

    with pytest.raises(
        database.CandidateJobAnalysisClaimLostError
    ):
        database.save_candidate_job_analysis_with_run(
            **common,
            analysis_claim_token="claim-a",
        )

    database.save_candidate_job_analysis_with_run(
        **common,
        analysis_claim_token="claim-b",
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
                analysis_state,
                analysis_claim_token,
                analysis_claimed_at,
                analysis_claim_expires_at
            FROM candidate_job_analyses
            WHERE
                candidate_id = 'candidate-1'
                AND job_id = 'job-1'
            """
        ).fetchone()

        run_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM candidate_job_analysis_runs
            """
        ).fetchone()[0]

    finally:
        connection.close()

    assert current[
        "recommendation"
    ] == "potential"

    assert current[
        "analysis_state"
    ] == "analyzed"

    assert current[
        "analysis_claim_token"
    ] is None

    assert current[
        "analysis_claimed_at"
    ] is None

    assert current[
        "analysis_claim_expires_at"
    ] is None

    assert run_count == 1


def test_reanalysis_claim_is_exclusive(
    monkeypatch,
    tmp_path,
):
    database_file = _prepare_database(
        monkeypatch,
        tmp_path,
    )

    connection = sqlite3.connect(
        database_file
    )

    try:
        connection.execute(
            """
            UPDATE candidate_job_analyses
            SET
                analysis_state = 'analyzed',
                evidence_signature = 'old-e',
                direction_signature = 'old-d',
                constraint_signature = 'old-c'
            WHERE
                candidate_id = 'candidate-1'
                AND job_id = 'job-1'
            """
        )

        connection.commit()

    finally:
        connection.close()

    first = (
        database.list_candidate_jobs_for_reanalysis(
            candidate_id="candidate-1",
            evidence_signature="new-e",
            direction_signature="new-d",
            constraint_signature="new-c",
            limit=1,
            claim_token="reclaim-a",
            claim_ttl_seconds=600,
        )
    )

    second = (
        database.list_candidate_jobs_for_reanalysis(
            candidate_id="candidate-1",
            evidence_signature="new-e",
            direction_signature="new-d",
            constraint_signature="new-c",
            limit=1,
            claim_token="reclaim-b",
            claim_ttl_seconds=600,
        )
    )

    assert len(first) == 1

    assert first[0][
        "analysis_claim_token"
    ] == "reclaim-a"

    assert first[0][
        "reanalysis_reasons"
    ] == [
        "evidence",
        "direction",
        "constraint",
    ]

    assert second == []
