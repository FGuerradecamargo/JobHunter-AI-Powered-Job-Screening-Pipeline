from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.database import get_connection


MIN_COMPLETE_ABSENCES = 2
COVERAGE_RECENT_HOURS = 48


class JobArchiveService:

    def archive_stale_global_jobs(
        self,
        stale_after_days: int = 30,
        now: datetime | None = None,
    ) -> int:
        if stale_after_days < 1:
            raise ValueError("Archive age must be positive.")
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("Archive time must be timezone-aware.")
        now = now.astimezone(timezone.utc)
        cutoff = (
            now
            - timedelta(days=stale_after_days)
        ).isoformat()

        archived_at = (
            now
            .isoformat()
        )

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET archived_at = ?
                WHERE
                    archived_at IS NULL
                    AND EXISTS (SELECT 1 FROM job_sources js WHERE js.job_id=jobs.id)
                    AND NOT EXISTS (
                        SELECT 1 FROM job_sources js WHERE js.job_id=jobs.id
                        AND (
                            js.user_id IS NOT NULL OR js.last_seen_at IS NULL OR js.last_seen_at >= ?
                            OR NOT EXISTS (
                                SELECT 1 FROM source_ingestion_runs latest
                                JOIN company_job_sources cs ON cs.id=latest.company_source_id
                                JOIN source_ingestion_state ss ON ss.source_identity=latest.source_identity
                                WHERE latest.source_identity=js.source_type
                                  AND cs.enabled=1 AND cs.source_type IN ('lever','ashby')
                                  AND ss.active_run_id IS NULL
                                  AND latest.started_at=ss.last_attempt_at
                                  AND latest.status='success' AND latest.coverage_complete=1
                                  AND latest.finished_at >= ?
                                  AND (
                                      SELECT COUNT(*) FROM source_ingestion_runs r
                                      WHERE r.source_identity=js.source_type
                                        AND r.company_source_id=cs.id
                                        AND r.status='success' AND r.coverage_complete=1
                                        AND r.started_at > js.last_seen_at
                                  ) >= ?
                            )
                        )
                    )
                """,
                (
                    archived_at,
                    cutoff,
                    (now - timedelta(hours=COVERAGE_RECENT_HOURS)).isoformat(),
                    MIN_COMPLETE_ABSENCES,
                ),
            )

        return cursor.rowcount

    def reactivate_seen_global_jobs(
        self,
    ) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET archived_at = NULL
                WHERE
                    archived_at IS NOT NULL
                    AND id IN (
                        SELECT DISTINCT job_id
                        FROM job_sources
                        WHERE
                            user_id IS NULL
                            AND last_seen_at IS NOT NULL
                            AND last_seen_at >= archived_at
                    )
                """
            )

        return cursor.rowcount
