from models.career_update import CareerUpdate
from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


class CareerUpdateRepository:
    def __init__(self) -> None:
        initialize_database()

    def save(
        self,
        career_update: CareerUpdate,
    ) -> None:
        created_at = (
            career_update.created_at
            or utc_now()
        )

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO candidate_career_updates (
                    id,
                    candidate_id,
                    update_type,
                    description,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s
                )

                ON CONFLICT(id) DO UPDATE SET
                    update_type = excluded.update_type,
                    description = excluded.description,
                    created_at = excluded.created_at
                """,
                (
                    career_update.id,
                    career_update.candidate_id,
                    career_update.update_type,
                    career_update.description,
                    created_at,
                ),
            )

    def list_for_candidate(
        self,
        candidate_id: str,
    ) -> list[CareerUpdate]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM candidate_career_updates
                WHERE candidate_id = %s
                ORDER BY created_at ASC
                """,
                (candidate_id,),
            ).fetchall()

        return [
            CareerUpdate(
                id=row["id"],
                candidate_id=row[
                    "candidate_id"
                ],
                update_type=row[
                    "update_type"
                ],
                description=row[
                    "description"
                ],
                created_at=row[
                    "created_at"
                ],
            )
            for row in rows
        ]

    def delete(
        self,
        update_id: str,
    ) -> bool:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM candidate_career_updates
                WHERE id = %s
                """,
                (update_id,),
            )

        return cursor.rowcount > 0
