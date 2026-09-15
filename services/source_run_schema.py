"""Portable, server-only scheduler state and bounded operational run records."""


def create_source_run_schema(connection):
    from services.database import _enable_server_only_row_level_security
    connection.execute("""
        CREATE TABLE IF NOT EXISTS source_ingestion_state (
            source_identity TEXT PRIMARY KEY,
            active_run_id TEXT,
            lease_expires_at TEXT,
            next_eligible_at TEXT,
            last_attempt_at TEXT,
            last_success_at TEXT
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS source_ingestion_runs (
            id TEXT PRIMARY KEY,
            source_identity TEXT NOT NULL,
            source_type TEXT NOT NULL,
            company_source_id TEXT REFERENCES company_job_sources(id) ON DELETE SET NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL CHECK(status IN ('running','success','partial','failed','expired')),
            jobs_fetched INTEGER NOT NULL DEFAULT 0,
            jobs_created INTEGER NOT NULL DEFAULT 0,
            jobs_updated INTEGER NOT NULL DEFAULT 0,
            jobs_unchanged INTEGER NOT NULL DEFAULT 0,
            failed_queries INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            next_eligible_at TEXT,
            coverage_complete INTEGER NOT NULL DEFAULT 0 CHECK(coverage_complete IN (0,1)),
            duration_seconds REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_source_runs_coverage
                          ON source_ingestion_runs(source_identity, started_at, coverage_complete)""")
    for table in ("source_ingestion_state", "source_ingestion_runs"):
        _enable_server_only_row_level_security(connection, table)
