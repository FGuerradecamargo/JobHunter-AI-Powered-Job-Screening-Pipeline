"""Additive provenance migration; legacy jobs are deliberately not backfilled."""


def migrate_job_observations(connection, *, postgres=False):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS job_observations (
            observation_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL,
            external_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_observations_owner ON job_observations(user_id, job_id)")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS job_content_authority (
            job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
            observation_id TEXT NOT NULL REFERENCES job_observations(observation_id) ON DELETE CASCADE
        )
    """)
    if postgres:
        for table in ("job_observations", "job_content_authority"):
            connection.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            connection.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                connection.execute(f"""DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                        REVOKE ALL ON TABLE {table} FROM {role};
                    END IF;
                END $$""")
