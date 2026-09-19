import json
from uuid import uuid4

from models.candidate_onboarding import CandidateOnboarding
from models.work_experience import WorkExperience
from models.company_interview import ConfirmedCompanyAnswer, validate_answers
from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


class CandidateOnboardingRepository:
    def __init__(self) -> None:
        initialize_database()

    def confirm_company_interview(self, *, candidate_id, company, start_date, end_date, answers, experience_id):
        validate_answers(answers)
        if not candidate_id or not experience_id or not company.strip() or (end_date and end_date < start_date):
            raise ValueError('Invalid company metadata.')
        projection = '\n\n'.join(f'[{a.question_id.upper()}] {a.question_text}\n{a.confirmed_text}'
            for a in answers if not a.skipped)
        now = utc_now()
        with get_connection() as connection:
            existing = connection.execute('SELECT candidate_id FROM candidate_work_experiences WHERE id = ?',
                (experience_id,)).fetchone()
            if existing:
                if existing['candidate_id'] != candidate_id:
                    raise ValueError('Work experience was not found for candidate.')
                return  # Idempotent confirmation after a successful save/rerun.
            connection.execute('''INSERT INTO candidate_work_experiences
                (id, candidate_id, company, start_date, end_date, career_story, day_to_day_narrative, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (experience_id, candidate_id, company.strip(), start_date, end_date, '', projection, now, now))
            for a in answers:
                connection.execute('''INSERT INTO company_interview_answers
                    (candidate_id, work_experience_id, interview_version, question_id, question_version,
                     question_text, answer_mode, confirmed_text, skipped, confirmed_at, source_kind)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (candidate_id, experience_id, a.interview_version, a.question_id, a.question_version,
                     a.question_text, a.answer_mode, a.confirmed_text, int(a.skipped), now, a.source_kind))

    def list_company_answers(self, candidate_id, experience_id, *, include_history=False):
        with get_connection() as connection:
            rows = connection.execute('''SELECT a.* FROM company_interview_answers a
                JOIN candidate_work_experiences e ON e.id = a.work_experience_id AND e.candidate_id = a.candidate_id
                WHERE a.candidate_id = ? AND a.work_experience_id = ? ORDER BY a.question_id''',
                (candidate_id, experience_id)).fetchall()
        edits = [r for r in rows if r['source_kind'] == 'USER_CONFIRMED_EDIT']
        if edits and not include_history:
            rows = [edits[-1]]
        return [ConfirmedCompanyAnswer(r['question_id'], r['question_text'], r['answer_mode'],
            r['confirmed_text'], bool(r['skipped']), r['interview_version'], r['question_version'], r['source_kind']) for r in rows]

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
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )

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
            day_to_day_narrative=(
                day_to_day_narrative.strip()
            ),
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
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
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
                confirmed_interview_answers=self.list_company_answers(candidate_id, row['id']),
            )
            for row in rows
        ]

    def update_work_experience(
        self,
        experience: WorkExperience,
        *,
        confirmed_source_edit: bool = False,
    ) -> None:
        now = utc_now()

        with get_connection() as connection:
            original = connection.execute(
                'SELECT * FROM candidate_work_experiences WHERE id = ? AND candidate_id = ?',
                (experience.id, experience.candidate_id),
            ).fetchone()
            if original is None:
                raise ValueError('Work experience was not found for candidate.')
            guided = connection.execute(
                'SELECT 1 FROM company_interview_answers WHERE work_experience_id = ? AND candidate_id = ?',
                (experience.id, experience.candidate_id),
            ).fetchone() is not None
            changed = any(original[field] != getattr(experience, field).strip()
                for field in ('career_story', 'day_to_day_narrative'))
            if guided and changed and confirmed_source_edit is not True:
                raise ValueError('Confirm your source corrections before saving.')
            cursor = connection.execute(
                """
                UPDATE candidate_work_experiences
                SET
                    company = ?,
                    start_date = ?,
                    end_date = ?,
                    career_story = ?,
                    day_to_day_narrative = ?,
                    updated_at = ?
                WHERE
                    id = ?
                    AND candidate_id = ?
                """,
                (
                    experience.company.strip(),
                    experience.start_date,
                    experience.end_date,
                    experience.career_story.strip(),
                    experience.day_to_day_narrative.strip(),
                    now,
                    experience.id,
                    experience.candidate_id,
                ),
            )
            if guided and confirmed_source_edit is True:
                # The UPDATE locks the experience before allocating its next revision.
                # Preserve original answers and every previous user correction.
                revision = connection.execute(
                    "SELECT COUNT(*) AS n FROM company_interview_answers WHERE candidate_id = ? "
                    "AND work_experience_id = ? AND source_kind = 'USER_CONFIRMED_EDIT'",
                    (experience.candidate_id, experience.id),
                ).fetchone()['n'] + 1
                if changed or revision == 1:
                    connection.execute('''INSERT INTO company_interview_answers
                        (candidate_id, work_experience_id, interview_version, question_id, question_version,
                         question_text, answer_mode, confirmed_text, skipped, confirmed_at, source_kind)
                        VALUES (?, ?, ?, ?, ?, ?, 'text', ?, 0, ?, 'USER_CONFIRMED_EDIT')''',
                        (experience.candidate_id, experience.id, 'experience-edit-v1',
                         f'user_edit_{revision:08d}', 'experience-edit-v1',
                         'User-confirmed replacement account of this experience',
                         json.dumps({'career_story': experience.career_story.strip(),
                                     'day_to_day_narrative': experience.day_to_day_narrative.strip()},
                                    ensure_ascii=False), now))

        if cursor.rowcount != 1:
            raise ValueError(
                "Work experience was not found for candidate."
            )

    def delete_work_experience(
        self,
        experience_id: str,
        candidate_id: str,
    ) -> None:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM candidate_work_experiences
                WHERE
                    id = ?
                    AND candidate_id = ?
                """,
                (
                    experience_id,
                    candidate_id,
                ),
            )

        if cursor.rowcount != 1:
            raise ValueError(
                "Work experience was not found for candidate."
            )
