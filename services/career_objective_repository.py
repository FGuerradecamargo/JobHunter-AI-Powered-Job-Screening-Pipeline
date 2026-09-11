import json

from models.career_objective import CareerObjective
from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


class CareerObjectiveRepository:
    def __init__(self) -> None:
        initialize_database()

    def save(
        self,
        objective: CareerObjective,
    ) -> None:
        now = utc_now()

        created_at = (
            objective.created_at
            or now
        )

        with get_connection() as connection:
            if objective.active:
                connection.execute(
                    """
                    UPDATE candidate_career_objectives
                    SET active = 0,
                        updated_at = ?
                    WHERE candidate_id = ?
                      AND id <> ?
                      AND active = 1
                    """,
                    (
                        now,
                        objective.candidate_id,
                        objective.id,
                    ),
                )

            cursor = connection.execute(
                """
                INSERT INTO candidate_career_objectives (
                    id,
                    candidate_id,
                    title,
                    description,
                    active,
                    desired_role_families_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?
                )

                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    active = excluded.active,
                    desired_role_families_json = excluded.desired_role_families_json,
                    updated_at = excluded.updated_at
                WHERE
                    candidate_career_objectives.candidate_id
                        = excluded.candidate_id
                """,
                (
                    objective.id,
                    objective.candidate_id,
                    objective.title,
                    objective.description,
                    int(objective.active),
                    json.dumps(
                        objective.desired_role_families,
                        ensure_ascii=False,
                    ),
                    created_at,
                    now,
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    "Career objective was not found for candidate."
                )

    def get_active(
        self,
        candidate_id: str,
    ) -> CareerObjective | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM candidate_career_objectives
                WHERE candidate_id = ?
                  AND active = 1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (candidate_id,),
            ).fetchone()

        if row is None:
            return None

        return self._from_row(row)

    def list_for_candidate(
        self,
        candidate_id: str,
    ) -> list[CareerObjective]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM candidate_career_objectives
                WHERE candidate_id = ?
                ORDER BY created_at ASC
                """,
                (candidate_id,),
            ).fetchall()

        return [
            self._from_row(row)
            for row in rows
        ]

    def deactivate_all(
        self,
        candidate_id: str,
    ) -> None:
        now = utc_now()

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE candidate_career_objectives
                SET active = 0,
                    updated_at = ?
                WHERE candidate_id = ?
                """,
                (
                    now,
                    candidate_id,
                ),
            )

    @staticmethod
    def _from_row(
        row,
    ) -> CareerObjective:
        return CareerObjective(
            id=row["id"],
            candidate_id=row[
                "candidate_id"
            ],
            title=row["title"],
            description=row[
                "description"
            ],
            active=bool(
                row["active"]
            ),
            desired_role_families=json.loads(
                row[
                    "desired_role_families_json"
                ]
                or "[]"
            ),
            created_at=row[
                "created_at"
            ],
            updated_at=row[
                "updated_at"
            ],
        )
