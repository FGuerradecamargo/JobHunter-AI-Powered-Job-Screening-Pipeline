from __future__ import annotations

from dataclasses import asdict
from typing import Any

from models.application_outcome import ApplicationOutcome
from services.database import get_connection


class ApplicationOutcomeRepository:
    def get_application(
        self,
        candidate_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT candidate_id, job_id, status, opportunity_state,
                       applied_at
                FROM candidate_job_analyses
                WHERE candidate_id = ? AND job_id = ?
                """,
                (candidate_id, job_id),
            ).fetchone()

        return dict(row) if row is not None else None

    def get(
        self,
        candidate_id: str,
        job_id: str,
    ) -> ApplicationOutcome | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM candidate_application_outcomes
                WHERE candidate_id = ? AND job_id = ?
                """,
                (candidate_id, job_id),
            ).fetchone()

        return ApplicationOutcome(**dict(row)) if row is not None else None

    def save(self, outcome: ApplicationOutcome) -> ApplicationOutcome:
        values = asdict(outcome)
        with get_connection() as connection:
            relationship = connection.execute(
                """
                SELECT 1
                FROM candidate_job_analyses
                WHERE candidate_id = ? AND job_id = ?
                """,
                (outcome.candidate_id, outcome.job_id),
            ).fetchone()
            if relationship is None:
                raise ValueError(
                    "Candidate-job relationship was not found: "
                    f"{outcome.candidate_id} / {outcome.job_id}"
                )

            connection.execute(
                """
                INSERT INTO candidate_application_outcomes (
                    candidate_id, job_id, final_status, interview_stage,
                    rejection_reason, recruiter_feedback, candidate_notes,
                    offer_salary, offer_currency, lessons_learned,
                    outcome_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id, job_id)
                DO UPDATE SET
                    final_status = excluded.final_status,
                    interview_stage = excluded.interview_stage,
                    rejection_reason = excluded.rejection_reason,
                    recruiter_feedback = excluded.recruiter_feedback,
                    candidate_notes = excluded.candidate_notes,
                    offer_salary = excluded.offer_salary,
                    offer_currency = excluded.offer_currency,
                    lessons_learned = excluded.lessons_learned,
                    outcome_date = excluded.outcome_date,
                    updated_at = excluded.updated_at
                """,
                tuple(values[field] for field in (
                    "candidate_id", "job_id", "final_status",
                    "interview_stage", "rejection_reason",
                    "recruiter_feedback", "candidate_notes", "offer_salary",
                    "offer_currency", "lessons_learned", "outcome_date",
                    "created_at", "updated_at",
                )),
            )

        saved = self.get(outcome.candidate_id, outcome.job_id)
        if saved is None:
            raise RuntimeError("Application outcome could not be read after save")
        return saved
