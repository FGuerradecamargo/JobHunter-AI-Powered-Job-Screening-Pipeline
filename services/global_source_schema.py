from __future__ import annotations

from psycopg import sql


def ensure_global_source_schema(connection, *, postgres: bool) -> None:
    """Upgrade existing provenance in place, preserving personal observations."""
    if postgres:
        connection.execute("SELECT pg_advisory_xact_lock(731302)")
        key = connection.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'job_sources'::regclass AND contype = 'p'
            """
        ).fetchone()
        columns = connection.execute(
            """
            SELECT a.attname AS column_name
            FROM pg_constraint c
            JOIN unnest(c.conkey) WITH ORDINALITY AS cols(attnum, ord) ON TRUE
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = cols.attnum
            WHERE c.conrelid = 'job_sources'::regclass AND c.contype = 'p'
            ORDER BY cols.ord
            """
        ).fetchall()
        connection.execute(
            "ALTER TABLE job_sources ADD COLUMN IF NOT EXISTS source_id BIGSERIAL"
        )
        if key and [row["column_name"] for row in columns] != ["source_id"]:
            # Constraint names come from the catalog and must be SQL identifiers.
            connection.execute(sql.SQL("ALTER TABLE job_sources DROP CONSTRAINT {}").format(
                sql.Identifier(key["conname"])
            ))
            key = None
        connection.execute("ALTER TABLE job_sources ALTER COLUMN user_id DROP NOT NULL")
        if key is None:
            connection.execute("ALTER TABLE job_sources ADD PRIMARY KEY (source_id)")
        connection.execute("ALTER TABLE job_sources ADD COLUMN IF NOT EXISTS last_seen_at TEXT")
        connection.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS archived_at TEXT")
    else:
        columns = {row["name"]: row for row in connection.execute(
            "PRAGMA table_info(job_sources)"
        ).fetchall()}
        if columns["user_id"]["notnull"]:
            # SQLite cannot drop NOT NULL in place; copy only this legacy table.
            connection.execute("""
                CREATE TABLE job_sources_v2 (
                    source_id INTEGER PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                    source_type TEXT NOT NULL,
                    discovered_at TEXT NOT NULL,
                    last_seen_at TEXT
                )
            """)
            activity = "COALESCE(last_seen_at, discovered_at)" if "last_seen_at" in columns else "discovered_at"
            connection.execute(f"""
                INSERT INTO job_sources_v2 (
                    job_id, user_id, source_type, discovered_at, last_seen_at
                )
                SELECT job_id, user_id, source_type, discovered_at, {activity}
                FROM job_sources
            """)
            connection.execute("DROP TABLE job_sources")
            connection.execute("ALTER TABLE job_sources_v2 RENAME TO job_sources")
        elif "last_seen_at" not in columns:
            connection.execute("ALTER TABLE job_sources ADD COLUMN last_seen_at TEXT")
        job_columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        if "archived_at" not in job_columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN archived_at TEXT")

    connection.execute("""
        UPDATE job_sources SET last_seen_at = discovered_at WHERE last_seen_at IS NULL
    """)
    for name in ("ux_job_sources_global_source", "ux_job_sources_user_source"):
        connection.execute(f"DROP INDEX IF EXISTS {name}")
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_job_sources_personal
        ON job_sources(job_id, user_id, source_type) WHERE user_id IS NOT NULL
    """)
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_job_sources_global
        ON job_sources(job_id, source_type) WHERE user_id IS NULL
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_sources_user_id ON job_sources(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_sources_job_id ON job_sources(job_id)")
