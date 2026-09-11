import json

from models.application_contract import ApplicationAnalysisSource
from services.database import get_connection


class ApplicationContractSourceRepository:
    def get_analysis_source(
        self,
        candidate_id: str,
        job_id: str,
    ) -> ApplicationAnalysisSource | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    candidate_job_analyses.candidate_id,
                    candidate_job_analyses.job_id,
                    candidate_job_analyses.recommendation,
                    candidate_job_analyses.analysis_json,
                    jobs.title,
                    jobs.company,
                    jobs.location,
                    jobs.url,
                    jobs.remote,
                    jobs.salary,
                    jobs.description,
                    jobs.raw_text
                FROM candidate_job_analyses
                INNER JOIN jobs
                    ON jobs.id = candidate_job_analyses.job_id
                WHERE candidate_job_analyses.candidate_id = ?
                  AND candidate_job_analyses.job_id = ?
                  AND candidate_job_analyses.analysis_state = 'analyzed'
                """,
                (candidate_id, job_id),
            ).fetchone()

            run = connection.execute(
                """
                SELECT id
                FROM candidate_job_analysis_runs
                WHERE candidate_id = ?
                  AND job_id = ?
                  AND result_state = 'completed'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (candidate_id, job_id),
            ).fetchone()

        if row is None:
            return None

        try:
            analysis = json.loads(row["analysis_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            analysis = {}

        analysis_id = (
            str(run["id"])
            if run is not None
            else f"candidate-job-analysis:{candidate_id}:{job_id}"
        )
        return ApplicationAnalysisSource(
            candidate_id=str(row["candidate_id"]),
            job_id=str(row["job_id"]),
            analysis_id=analysis_id,
            recommendation=str(row["recommendation"] or ""),
            job={
                "id": row["job_id"],
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "url": row["url"],
                "remote": row["remote"],
                "salary": row["salary"],
                "description": row["description"],
                "raw_text": row["raw_text"],
            },
            analysis=analysis if isinstance(analysis, dict) else {},
        )

