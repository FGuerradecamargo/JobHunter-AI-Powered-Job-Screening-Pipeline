from __future__ import annotations

from dataclasses import asdict
import json

from models.interview_feedback import InterviewFeedback
from services.database import get_connection, utc_now


class InterviewFeedbackDataError(ValueError):
    pass


def _string_list(value, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise InterviewFeedbackDataError(f"{field_name} must be a JSON list.")
    if any(not isinstance(item, str) for item in value):
        raise InterviewFeedbackDataError(f"{field_name} must contain only text.")
    return value


class InterviewFeedbackRepository:
    def get(self, candidate_id: str, job_id: str) -> InterviewFeedback | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM candidate_interview_feedback
                WHERE candidate_id = ? AND job_id = ?
                """,
                (candidate_id, job_id),
            ).fetchone()
        if row is None:
            return None
        values = dict(row)
        try:
            values["discussed_topics"] = _string_list(
                json.loads(values.pop("discussed_topics_json") or "[]"),
                "discussed_topics",
            )
            values["difficult_topics"] = _string_list(
                json.loads(values.pop("difficult_topics_json") or "[]"),
                "difficult_topics",
            )
        except (json.JSONDecodeError, TypeError) as exc:
            raise InterviewFeedbackDataError(
                "Stored interview feedback topics are malformed."
            ) from exc
        return InterviewFeedback(**values)

    def save(self, feedback: InterviewFeedback) -> InterviewFeedback:
        if not feedback.candidate_id.strip() or not feedback.job_id.strip():
            raise ValueError("candidate_id and job_id must be non-empty.")
        if feedback.interview_stage not in {"interview", "final_interview"}:
            raise ValueError("Feedback requires an active interview stage.")
        _string_list(feedback.discussed_topics, "discussed_topics")
        _string_list(feedback.difficult_topics, "difficult_topics")

        values = asdict(feedback)
        now = utc_now()
        created_at = feedback.created_at or now
        with get_connection() as connection:
            relationship = connection.execute(
                """
                SELECT 1 FROM candidate_job_analyses
                WHERE candidate_id = ? AND job_id = ?
                """,
                (feedback.candidate_id, feedback.job_id),
            ).fetchone()
            if relationship is None:
                raise ValueError("Candidate-job relationship was not found.")
            connection.execute(
                """
                INSERT INTO candidate_interview_feedback (
                    candidate_id, job_id, interview_stage, recruiter_feedback,
                    candidate_notes, discussed_topics_json,
                    difficult_topics_json, next_stage_instructions,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id, job_id) DO UPDATE SET
                    interview_stage = excluded.interview_stage,
                    recruiter_feedback = excluded.recruiter_feedback,
                    candidate_notes = excluded.candidate_notes,
                    discussed_topics_json = excluded.discussed_topics_json,
                    difficult_topics_json = excluded.difficult_topics_json,
                    next_stage_instructions = excluded.next_stage_instructions,
                    updated_at = excluded.updated_at
                """,
                (
                    values["candidate_id"], values["job_id"],
                    values["interview_stage"], values["recruiter_feedback"],
                    values["candidate_notes"],
                    json.dumps(values["discussed_topics"]),
                    json.dumps(values["difficult_topics"]),
                    values["next_stage_instructions"], created_at, now,
                ),
            )
        saved = self.get(feedback.candidate_id, feedback.job_id)
        if saved is None:
            raise RuntimeError("Interview feedback could not be read after save.")
        return saved
