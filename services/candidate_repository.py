import json
from dataclasses import asdict

from models.candidate import Candidate
from models.candidate_constraints import CandidateConstraints
from models.candidate_preferences import CandidatePreferences
from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


class CandidateRepository:
    def __init__(self) -> None:
        initialize_database()

    def save(
        self,
        candidate: Candidate,
    ) -> None:
        now = utc_now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO candidates (
                    id,
                    name,
                    current_role,
                    current_level,
                    professional_summary,
                    target_roles_json,
                    spoken_languages_json,
                    skills_json,
                    strengths_json,
                    development_areas_json,
                    preferences_json,
                    constraints_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    current_role = excluded.current_role,
                    current_level = excluded.current_level,
                    professional_summary = excluded.professional_summary,
                    target_roles_json = excluded.target_roles_json,
                    spoken_languages_json = excluded.spoken_languages_json,
                    skills_json = excluded.skills_json,
                    strengths_json = excluded.strengths_json,
                    development_areas_json = excluded.development_areas_json,
                    preferences_json = excluded.preferences_json,
                    constraints_json = excluded.constraints_json,
                    updated_at = excluded.updated_at
                """,
                (
                    candidate.id,
                    candidate.name,
                    candidate.current_role,
                    candidate.current_level,
                    candidate.professional_summary,
                    json.dumps(
                        candidate.target_roles,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        candidate.spoken_languages,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        candidate.skills,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        candidate.strengths,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        candidate.development_areas,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        asdict(candidate.preferences),
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        asdict(candidate.constraints),
                        ensure_ascii=False,
                    ),
                    now,
                    now,
                ),
            )

    def get(
        self,
        candidate_id: str,
    ) -> Candidate | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM candidates
                WHERE id = ?
                """,
                (candidate_id,),
            ).fetchone()

        if row is None:
            return None

        return self._from_row(row)

    def list_all(
        self,
    ) -> list[Candidate]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM candidates
                ORDER BY name
                """
            ).fetchall()

        return [
            self._from_row(row)
            for row in rows
        ]

    def delete(
        self,
        candidate_id: str,
    ) -> bool:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM candidates
                WHERE id = ?
                """,
                (candidate_id,),
            )

        return cursor.rowcount > 0

    def exists(
        self,
        candidate_id: str,
    ) -> bool:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM candidates
                WHERE id = ?
                """,
                (candidate_id,),
            ).fetchone()

        return row is not None

    @staticmethod
    def _from_row(
        row,
    ) -> Candidate:
        return Candidate(
            id=row["id"],
            name=row["name"],
            current_role=row["current_role"],
            current_level=row["current_level"],
            professional_summary=row[
                "professional_summary"
            ],
            target_roles=json.loads(
                row["target_roles_json"]
            ),
            spoken_languages=json.loads(
                row["spoken_languages_json"]
            ),
            skills=json.loads(
                row["skills_json"]
            ),
            strengths=json.loads(
                row["strengths_json"]
            ),
            development_areas=json.loads(
                row["development_areas_json"]
            ),
            preferences=CandidatePreferences(
                **json.loads(
                    row["preferences_json"]
                )
            ),
            constraints=CandidateConstraints(
                **json.loads(
                    row["constraints_json"]
                )
            ),
        )