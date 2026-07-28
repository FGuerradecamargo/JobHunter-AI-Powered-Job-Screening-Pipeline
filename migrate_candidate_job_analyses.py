import sqlite3

from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


CANDIDATE_ID = "felipe"


def candidate_exists(
    connection: sqlite3.Connection,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM candidates
        WHERE id = ?
        """,
        (CANDIDATE_ID,),
    ).fetchone()

    return row is not None


def migrate_analyses() -> tuple[int, int]:
    initialize_database()

    migrated = 0
    skipped = 0

    with get_connection() as connection:
        if not candidate_exists(connection):
            raise RuntimeError(
                f"Candidate '{CANDIDATE_ID}' "
                "was not found."
            )

        rows = connection.execute(
            """
            SELECT
                id,
                recommendation,
                competitive_status,
                current_fit,
                growth_value,
                analysis_json,
                status,
                notes,
                created_at,
                updated_at,
                applied_at,
                rejected_at
            FROM jobs
            WHERE analysis_json IS NOT NULL
            """
        ).fetchall()

        for row in rows:
            analysis_json = row["analysis_json"]

            if not analysis_json:
                skipped += 1
                continue

            now = utc_now()

            connection.execute(
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
                    updated_at,
                    applied_at,
                    rejected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(
                    candidate_id,
                    job_id
                )
                DO UPDATE SET
                    recommendation =
                        excluded.recommendation,
                    competitive_status =
                        excluded.competitive_status,
                    current_fit =
                        excluded.current_fit,
                    growth_value =
                        excluded.growth_value,
                    analysis_json =
                        excluded.analysis_json,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    CANDIDATE_ID,
                    row["id"],
                    row["recommendation"],
                    row["competitive_status"],
                    row["current_fit"],
                    row["growth_value"],
                    analysis_json,
                    row["status"] or "in_review",
                    row["notes"] or "",
                    row["created_at"] or now,
                    row["updated_at"] or now,
                    row["applied_at"],
                    row["rejected_at"],
                ),
            )

            migrated += 1

    return migrated, skipped


def main() -> None:
    migrated, skipped = migrate_analyses()

    print("=" * 60)
    print("JOBHUNTER — ANALYSIS MIGRATION")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_ID}")
    print(f"Analyses migrated: {migrated}")
    print(f"Rows skipped: {skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()