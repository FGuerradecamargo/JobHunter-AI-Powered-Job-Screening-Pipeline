from __future__ import annotations

from typing import Any

from services.database import get_connection


class ApplicationLifecycleRepository:
    def get(self, candidate_id: str, job_id: str) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    candidate_id,
                    job_id,
                    status,
                    opportunity_state,
                    applied_at,
                    rejected_at
                FROM candidate_job_analyses
                WHERE candidate_id = ? AND job_id = ?
                """,
                (candidate_id, job_id),
            ).fetchone()

        return dict(row) if row is not None else None

    def mark_applied(
        self,
        candidate_id: str,
        job_id: str,
        applied_at: str,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE candidate_job_analyses
                SET
                    status = 'applied',
                    opportunity_state = 'applied',
                    updated_at = ?,
                    applied_at = COALESCE(applied_at, ?)
                WHERE candidate_id = ? AND job_id = ?
                """,
                (applied_at, applied_at, candidate_id, job_id),
            )
            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                """
                SELECT
                    candidate_id,
                    job_id,
                    status,
                    opportunity_state,
                    applied_at,
                    rejected_at
                FROM candidate_job_analyses
                WHERE candidate_id = ? AND job_id = ?
                """,
                (candidate_id, job_id),
            ).fetchone()

        return dict(row) if row is not None else None

    def mark_user_rejected(
        self,
        candidate_id: str,
        job_id: str,
        updated_at: str,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE candidate_job_analyses
                SET
                    status = 'user_rejected',
                    opportunity_state = 'user_rejected',
                    updated_at = ?
                WHERE candidate_id = ? AND job_id = ?
                """,
                (updated_at, candidate_id, job_id),
            )
            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                """
                SELECT
                    candidate_id,
                    job_id,
                    status,
                    opportunity_state,
                    applied_at,
                    rejected_at
                FROM candidate_job_analyses
                WHERE candidate_id = ? AND job_id = ?
                """,
                (candidate_id, job_id),
            ).fetchone()

        return dict(row) if row is not None else None
