import json
from uuid import uuid4

from models.candidate_onboarding import CandidateOnboarding
from models.work_experience import WorkExperience
from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


class CandidateOnboardingRepository:
    def __init__(self) -> None:
        initialize_database()

    def save_onboarding(
        self,
        onboarding: CandidateOnboarding,
    ) -> None:
        now = utc_now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO candidate_onboarding (
                    candidate_id,
                    location,
                    work_authorisation,
                    spoken_languages_json,
                    desired_next_work,
                    enjoyed_work,
                    avoid_work,
                    development_interests,
                    career_priorities_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(candidate_id) DO UPDATE SET
                    location = excluded.location,
                    work_authorisation = excluded.work_authorisation,
                    spoken_languages_json = excluded.spoken_languages_json,
                    desired_next_work = excluded.desired_next_work,
                    enjoyed_work = excluded.enjoyed_work,
                    avoid_work = excluded.avoid_work,
                    development_interests = excluded.development_interests,
                    career_priorities_json = excluded.career_priorities_json,
                    updated_at = excluded.updated_at
                """,
                (
                    onboarding.candidate_id,
                    onboarding.location,
                    onboarding.work_authorisation,
                    json.dumps(
                        onboarding.spoken_languages,
                        ensure_ascii=False,
                    ),
                    onboarding.desired_next_work,
                    onboarding.enjoyed_work,
                    onboarding.avoid_work,
                    onboarding.development_interests,
                    json.dumps(
                        onboarding.career_priorities,
                        ensure_ascii=False,
                    ),
                    now,
                    now,
                ),
            )

    def get_onboarding(
        self,
        candidate_id: str,
    ) -> CandidateOnboarding | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM candidate_onboarding
                WHERE candidate_id = ?
                """,
                (candidate_id,),
            ).fetchone()

        if row is None:
            return None

        return CandidateOnboarding(
            candidate_id=row["candidate_id"],
            location=row["location"],
            work_authorisation=row["work_authorisation"],
            spoken_languages=json.loads(
                row["spoken_languages_json"]
            ),
            desired_next_work=row["desired_next_work"],
            enjoyed_work=row["enjoyed_work"],
            avoid_work=row["avoid_work"],
            development_interests=row[
                "development_interests"
            ],
            career_priorities=json.loads(
                row["career_priorities_json"]
            ),
        )

    def add_work_experience(
        self,
        candidate_id: str,
        company: str,
        start_date: str,
        end_date: str | None,
        career_story: str,
        day_to_day_narrative: str,
    ) -> WorkExperience:
        experience = WorkExperience(
            id=uuid4().hex,
            candidate_id=candidate_id,
            company=company.strip(),
            start_date=start_date,
            end_date=end_date,
            career_story=career_story.strip(),
            day_to_day_narrative=day_to_day_narrative.strip(),
        )

        now = utc_now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO candidate_work_experiences (
                    id,
                    candidate_id,
                    company,
                    start_date,
                    end_date,
                    career_story,
                    day_to_day_narrative,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experience.id,
                    experience.candidate_id,
                    experience.company,
                    experience.start_date,
                    experience.end_date,
                    experience.career_story,
                    experience.day_to_day_narrative,
                    now,
                    now,
                ),
            )

        return experience

    def list_work_experiences(
        self,
        candidate_id: str,
    ) -> list[WorkExperience]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM candidate_work_experiences
                WHERE candidate_id = ?
                ORDER BY start_date DESC
                """,
                (candidate_id,),
            ).fetchall()

        return [
            WorkExperience(
                id=row["id"],
                candidate_id=row["candidate_id"],
                company=row["company"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                career_story=row["career_story"],
                day_to_day_narrative=row[
                    "day_to_day_narrative"
                ],
            )
            for row in rows
        ]

    def update_work_experience(
            self,
            experience: WorkExperience,
    ) -> None:
        now = utc_now()

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE candidate_work_experiences
                SET
                    company = ?,
                    start_date = ?,
                    end_date = ?,
                    career_story = ?,
                    day_to_day_narrative = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    experience.company.strip(),
                    experience.start_date,
                    experience.end_date,
                    experience.career_story.strip(),
                    experience.day_to_day_narrative.strip(),
                    now,
                    experience.id,
                ),
            )

    def delete_work_experience(
            self,
            experience_id: str,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                DELETE FROM candidate_work_experiences
                WHERE id = ?
                """,
                (experience_id,),
            )
