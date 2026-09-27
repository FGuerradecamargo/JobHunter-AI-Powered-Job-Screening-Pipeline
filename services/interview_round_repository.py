from __future__ import annotations

from uuid import uuid4
from dataclasses import replace
import json

from models.application_tracking import (
    InterviewRound,
    InterviewRoundFeedback,
)
from services.database import get_connection, utc_now


class InterviewRoundRepository:
    def create(
        self,
        *,
        candidate_id: str,
        job_id: str,
        scheduled_at: str,
        interviewer_names=(),
        interviewer_roles=(),
        interview_type: str = "",
        notes: str = "",
        interview_id: str | None = None,
    ) -> InterviewRound:
        if not candidate_id or not job_id:
            raise ValueError("Candidate and job are required.")
        now = utc_now()
        requested = InterviewRound(
            interview_id=interview_id or uuid4().hex, candidate_id=candidate_id,
            job_id=job_id, sequence=1, scheduled_at=scheduled_at,
            interviewer_names=tuple(interviewer_names or ()),
            interviewer_roles=tuple(interviewer_roles or ()), interview_type=interview_type,
            notes=notes, created_at=now, updated_at=now,
        )
        candidate_id, job_id = requested.candidate_id, requested.job_id

        with get_connection() as connection:
            # Serialize sequence allocation across tabs/workers on this relationship.
            connection.execute(
                "UPDATE candidate_job_analyses SET status = status WHERE candidate_id = ? AND job_id = ?",
                (candidate_id, job_id),
            )
            relationship = connection.execute(
                """SELECT status
                   FROM candidate_job_analyses
                   WHERE candidate_id = ? AND job_id = ?""",
                (candidate_id, job_id),
            ).fetchone()
            if relationship is None:
                raise ValueError(
                    "Candidate-job relationship was not found."
                )

            if interview_id:
                existing = connection.execute(
                    "SELECT * FROM candidate_interview_rounds WHERE interview_id = ?", (interview_id,),
                ).fetchone()
                if existing:
                    expected = (candidate_id, job_id, requested.scheduled_at, requested.interviewer_names,
                                requested.interviewer_roles, requested.interview_type, requested.notes)
                    actual = (existing["candidate_id"], existing["job_id"], existing["scheduled_at"],
                              tuple(json.loads(existing["interviewer_names_json"])), tuple(json.loads(existing["interviewer_roles_json"])),
                              existing["interview_type"], existing["notes"])
                    if expected != actual:
                        raise ValueError("Interview request conflicts with an existing round.")
                    return _round(existing)
            outcome = connection.execute(
                "SELECT final_status FROM candidate_application_outcomes WHERE candidate_id = ? AND job_id = ?",
                (candidate_id, job_id),
            ).fetchone()
            if relationship["status"] not in {"applied", "in_process"} or (outcome and outcome["final_status"]):
                raise ValueError("An active applied relationship is required.")

            sequence = connection.execute(
                """SELECT COALESCE(MAX(sequence), 0) + 1 AS n
                   FROM candidate_interview_rounds
                   WHERE candidate_id = ? AND job_id = ?""",
                (candidate_id, job_id),
            ).fetchone()["n"]

            item = replace(requested, sequence=int(sequence))

            connection.execute(
                """INSERT INTO candidate_interview_rounds
                   (interview_id, candidate_id, job_id, sequence,
                    scheduled_at, interviewer_names_json,
                    interviewer_roles_json, interview_type, notes,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.interview_id,
                    item.candidate_id,
                    item.job_id,
                    item.sequence,
                    item.scheduled_at,
                    json.dumps(item.interviewer_names),
                    json.dumps(item.interviewer_roles),
                    item.interview_type,
                    item.notes,
                    item.created_at,
                    item.updated_at,
                ),
            )
            # Creating a real round is an explicit interview event, not an age inference.
            connection.execute(
                """INSERT INTO candidate_application_outcomes
                   (candidate_id, job_id, interview_stage, created_at, updated_at, outcome_date)
                   VALUES (?, ?, 'interview', ?, ?, ?)
                   ON CONFLICT(candidate_id, job_id) DO UPDATE SET
                     interview_stage = 'interview', updated_at = excluded.updated_at,
                     outcome_date = excluded.outcome_date
                   WHERE candidate_application_outcomes.final_status = ''
                     AND candidate_application_outcomes.interview_stage = ''""",
                (candidate_id, job_id, now, now, now),
            )

        return item

    def list(
        self,
        candidate_id: str,
        job_id: str,
    ) -> list[InterviewRound]:
        with get_connection() as connection:
            rows = connection.execute(
                """SELECT *
                   FROM candidate_interview_rounds
                   WHERE candidate_id = ? AND job_id = ?
                   ORDER BY sequence ASC""",
                (candidate_id, job_id),
            ).fetchall()
        return [_round(row) for row in rows]

    def save_feedback(
        self,
        feedback: InterviewRoundFeedback,
    ) -> InterviewRoundFeedback:
        now = utc_now()
        with get_connection() as connection:
            round_row = connection.execute(
                """SELECT 1 FROM candidate_interview_rounds
                   WHERE interview_id = ? AND candidate_id = ? AND job_id = ?""",
                (feedback.interview_id, feedback.candidate_id, feedback.job_id),
            ).fetchone()
            if round_row is None:
                raise ValueError("Interview round was not found.")
            connection.execute(
                """INSERT INTO candidate_interview_round_feedback
                   (interview_id, candidate_id, job_id, feedback_text, next_steps, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(interview_id) DO UPDATE SET
                       feedback_text = excluded.feedback_text,
                       next_steps = excluded.next_steps,
                       updated_at = excluded.updated_at
                   WHERE candidate_interview_round_feedback.candidate_id = excluded.candidate_id
                     AND candidate_interview_round_feedback.job_id = excluded.job_id
                     AND (candidate_interview_round_feedback.feedback_text <> excluded.feedback_text
                          OR candidate_interview_round_feedback.next_steps <> excluded.next_steps)""",
                (feedback.interview_id, feedback.candidate_id, feedback.job_id,
                 feedback.feedback_text, feedback.next_steps, now, now),
            )
            saved = connection.execute(
                "SELECT * FROM candidate_interview_round_feedback WHERE interview_id = ? AND candidate_id = ? AND job_id = ?",
                (feedback.interview_id, feedback.candidate_id, feedback.job_id),
            ).fetchone()
        return InterviewRoundFeedback(**dict(saved))

    def feedback_for(self, interview_id, candidate_id, job_id):
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM candidate_interview_round_feedback WHERE interview_id = ? AND candidate_id = ? AND job_id = ?",
                (interview_id, candidate_id, job_id),
            ).fetchone()
        return InterviewRoundFeedback(**dict(row)) if row else None


def _round(row):
    values = dict(row)
    values["interviewer_names"] = tuple(json.loads(values.pop("interviewer_names_json")))
    values["interviewer_roles"] = tuple(json.loads(values.pop("interviewer_roles_json")))
    return InterviewRound(**values)
