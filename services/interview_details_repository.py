from __future__ import annotations

from dataclasses import asdict
import json

from models.interview_context import InterviewDetails
from services.database import get_connection, utc_now


class InterviewDetailsDataError(ValueError):
    pass


def _string_list(value, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise InterviewDetailsDataError(f"{field_name} must be a JSON list.")
    if any(not isinstance(item, str) for item in value):
        raise InterviewDetailsDataError(f"{field_name} must contain only text.")
    return value


class InterviewDetailsRepository:
    def get(self, candidate_id: str, job_id: str) -> InterviewDetails | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM candidate_interview_details
                WHERE candidate_id = ? AND job_id = ?
                """,
                (candidate_id, job_id),
            ).fetchone()
        if row is None:
            return None
        values = dict(row)
        try:
            values["explicit_topics"] = _string_list(
                json.loads(values.pop("explicit_topics_json") or "[]"),
                "explicit_topics",
            )
        except (json.JSONDecodeError, TypeError) as exc:
            raise InterviewDetailsDataError(
                "Stored interview topics are malformed."
            ) from exc
        return InterviewDetails(**values)

    def save(self, details: InterviewDetails) -> InterviewDetails:
        if not details.candidate_id.strip() or not details.job_id.strip():
            raise ValueError("candidate_id and job_id must be non-empty.")
        if details.duration_minutes is not None and details.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive when supplied.")
        _string_list(details.explicit_topics, "explicit_topics")

        now = utc_now()
        values = asdict(details)
        created_at = details.created_at or now
        with get_connection() as connection:
            relationship = connection.execute(
                """
                SELECT 1 FROM candidate_job_analyses
                WHERE candidate_id = ? AND job_id = ?
                """,
                (details.candidate_id, details.job_id),
            ).fetchone()
            if relationship is None:
                raise ValueError("Candidate-job relationship was not found.")
            connection.execute(
                """
                INSERT INTO candidate_interview_details (
                    candidate_id, job_id, interview_type, interview_format,
                    interviewer, duration_minutes, scheduled_at, instructions,
                    explicit_topics_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id, job_id) DO UPDATE SET
                    interview_type = excluded.interview_type,
                    interview_format = excluded.interview_format,
                    interviewer = excluded.interviewer,
                    duration_minutes = excluded.duration_minutes,
                    scheduled_at = excluded.scheduled_at,
                    instructions = excluded.instructions,
                    explicit_topics_json = excluded.explicit_topics_json,
                    updated_at = excluded.updated_at
                """,
                (
                    values["candidate_id"], values["job_id"],
                    values["interview_type"], values["interview_format"],
                    values["interviewer"], values["duration_minutes"],
                    values["scheduled_at"], values["instructions"],
                    json.dumps(values["explicit_topics"]), created_at, now,
                ),
            )
        saved = self.get(details.candidate_id, details.job_id)
        if saved is None:
            raise RuntimeError("Interview details could not be read after save.")
        return saved
