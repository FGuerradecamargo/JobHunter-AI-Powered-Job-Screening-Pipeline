import json
from dataclasses import asdict

from models.objective_profile import ObjectiveProfile
from models.professional_experience_profile import (
    ProfessionalExperienceProfile,
)
from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


class ObjectiveProfileRepository:
    def __init__(self) -> None:
        initialize_database()

    def save(
        self,
        profile: ObjectiveProfile,
    ) -> None:
        now = utc_now()

        with get_connection() as connection:
            existing = connection.execute(
                """
                SELECT created_at
                FROM candidate_objective_profiles
                WHERE objective_id = %s
                """,
                (profile.objective_id,),
            ).fetchone()

            created_at = (
                existing["created_at"]
                if existing is not None
                else now
            )

            connection.execute(
                """
                INSERT INTO candidate_objective_profiles (
                    objective_id,
                    candidate_id,
                    profile_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s
                )

                ON CONFLICT(objective_id) DO UPDATE SET
                    candidate_id = excluded.candidate_id,
                    profile_json = excluded.profile_json,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.objective_id,
                    profile.candidate_id,
                    json.dumps(
                        asdict(profile),
                        ensure_ascii=False,
                    ),
                    created_at,
                    now,
                ),
            )

    def get_for_objective(
        self,
        objective_id: str,
    ) -> ObjectiveProfile | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT profile_json
                FROM candidate_objective_profiles
                WHERE objective_id = %s
                """,
                (objective_id,),
            ).fetchone()

        if row is None:
            return None

        data = json.loads(
            row["profile_json"] or "{}"
        )

        data["relevant_experiences"] = [
            ProfessionalExperienceProfile(
                **experience
            )
            for experience in data.get(
                "relevant_experiences",
                [],
            )
        ]

        return ObjectiveProfile(
            **data
        )

    def get_active_for_candidate(
        self,
        candidate_id: str,
    ) -> ObjectiveProfile | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT op.profile_json
                FROM candidate_objective_profiles op
                JOIN candidate_career_objectives co
                  ON co.id = op.objective_id
                WHERE op.candidate_id = %s
                  AND co.active = 1
                ORDER BY co.updated_at DESC
                LIMIT 1
                """,
                (candidate_id,),
            ).fetchone()

        if row is None:
            return None

        data = json.loads(
            row["profile_json"] or "{}"
        )

        data["relevant_experiences"] = [
            ProfessionalExperienceProfile(
                **experience
            )
            for experience in data.get(
                "relevant_experiences",
                [],
            )
        ]

        return ObjectiveProfile(
            **data
        )
