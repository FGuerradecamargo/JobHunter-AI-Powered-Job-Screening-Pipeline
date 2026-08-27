from services.database import get_connection


def migrate() -> None:
    with get_connection() as connection:

        # -------------------------------------------------
        # job_sources: allow global sources
        # -------------------------------------------------

        connection.execute(
            """
            ALTER TABLE job_sources
            ALTER COLUMN user_id DROP NOT NULL
            """
        )

        connection.execute(
            """
            ALTER TABLE job_sources
            ADD COLUMN IF NOT EXISTS source_id BIGSERIAL
            """
        )

        # Find current primary key.
        pk_row = connection.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE
                conrelid = 'job_sources'::regclass
                AND contype = 'p'
            """
        ).fetchone()

        if pk_row:
            pk_name = pk_row["conname"]

            pk_columns = connection.execute(
                """
                SELECT a.attname AS column_name
                FROM pg_constraint c
                JOIN unnest(c.conkey)
                    WITH ORDINALITY AS cols(attnum, ord)
                    ON TRUE
                JOIN pg_attribute a
                    ON
                        a.attrelid = c.conrelid
                        AND a.attnum = cols.attnum
                WHERE
                    c.conrelid = 'job_sources'::regclass
                    AND c.contype = 'p'
                ORDER BY cols.ord
                """
            ).fetchall()

            columns = [
                row["column_name"]
                for row in pk_columns
            ]

            if columns != ["source_id"]:
                connection.execute(
                    f"""
                    ALTER TABLE job_sources
                    DROP CONSTRAINT "{pk_name}"
                    """
                )

                pk_row = None

        if not pk_row:
            connection.execute(
                """
                ALTER TABLE job_sources
                ADD PRIMARY KEY (source_id)
                """
            )

        # Remove legacy duplicate indexes.
        connection.execute(
            """
            DROP INDEX IF EXISTS
                ux_job_sources_global_source
            """
        )

        connection.execute(
            """
            DROP INDEX IF EXISTS
                ux_job_sources_user_source
            """
        )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_job_sources_personal
            ON job_sources (
                job_id,
                user_id,
                source_type
            )
            WHERE user_id IS NOT NULL
            """
        )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_job_sources_global
            ON job_sources (
                job_id,
                source_type
            )
            WHERE user_id IS NULL
            """
        )

        # -------------------------------------------------
        # Freshness
        # -------------------------------------------------

        connection.execute(
            """
            ALTER TABLE job_sources
            ADD COLUMN IF NOT EXISTS last_seen_at TEXT
            """
        )

        connection.execute(
            """
            UPDATE job_sources
            SET last_seen_at = discovered_at
            WHERE last_seen_at IS NULL
            """
        )

        # -------------------------------------------------
        # Job lifecycle
        # -------------------------------------------------

        connection.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN IF NOT EXISTS archived_at TEXT
            """
        )


def main() -> None:
    migrate()

    print("=" * 60)
    print("JOBHUNTER - GLOBAL JOB INGESTION MIGRATION")
    print("=" * 60)
    print("Migration completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
