from __future__ import annotations

from dataclasses import asdict
from typing import Any

from models.application_outcome import ApplicationOutcome
from services.database import get_connection


from services.runtime_timing import timed


class ApplicationOutcomeRepository:
    @timed("applications")
    def list_applications(self, candidate_id: str) -> list[dict[str, Any]]:
        """Read lifecycle and explicit outcomes together; age never changes an outcome."""
        from services.application_outcome_service import ApplicationOutcomeService
        import json

        with get_connection() as connection:
            rows = connection.execute(
                """SELECT j.id, j.title, j.company, j.location, j.url,
                          a.status, a.opportunity_state, a.notes, a.analysis_json, a.applied_at,
                          o.final_status, o.interview_stage,
                          (SELECT COUNT(*) FROM candidate_interview_rounds r
                           WHERE r.candidate_id = a.candidate_id AND r.job_id = a.job_id) AS round_count
                   FROM candidate_job_analyses a JOIN jobs j ON j.id = a.job_id
                   LEFT JOIN candidate_application_outcomes o
                     ON o.candidate_id = a.candidate_id AND o.job_id = a.job_id
                   WHERE a.candidate_id = ? AND
                     ((a.status = 'in_review' AND a.opportunity_state = 'ready_to_apply')
                      OR a.status IN ('applied', 'in_process', 'offer',
                                      'rejected_before_interview', 'rejected_after_interview'))
                   ORDER BY a.updated_at DESC, j.id""", (candidate_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["analysis"] = json.loads(item.pop("analysis_json") or "{}")
            except (ValueError, TypeError):
                item["analysis"] = {}
            state = item["final_status"] or item["interview_stage"]
            if not state:
                state = ("ready_to_apply" if item["status"] == "in_review" else
                         "interview" if item["round_count"] and item["status"] in {"applied", "in_process"} else
                         ApplicationOutcomeService.current_state(None, item["status"]))
            item["application_stage"] = state
            item["application_group"] = (
                "closed" if state in {"accepted", "declined", "rejected", "withdrawn"} else
                "interview" if state == "final_interview" else state
            )
            result.append(item)
        return result

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
            # Coordinate terminal outcomes with interview-round creation.
            connection.execute(
                "UPDATE candidate_job_analyses SET status = status WHERE candidate_id = ? AND job_id = ?",
                (outcome.candidate_id, outcome.job_id),
            )
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
