from dataclasses import asdict
import hashlib
import json

from models.job import Job
from models.job_profile import JobProfile
from services.ai.job_profile_service import JobProfileService
from services.database import get_connection, utc_now


JOB_PROFILE_VERSION = "job-profile-v1"


def build_job_profile_signature(job: Job) -> str:
    payload = {
        "title": job.title or "",
        "company": job.company or "",
        "location": job.location or "",
        "remote": job.remote,
        "salary": job.salary or "",
        "description": job.description or job.raw_text or "",
    }

    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


class JobProfileManager:

    def __init__(
        self,
        service: JobProfileService,
    ) -> None:
        self.service = service

    def ensure_table(self) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_profiles (
                    job_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    job_signature TEXT NOT NULL,
                    profile_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    FOREIGN KEY (job_id)
                        REFERENCES jobs(id)
                        ON DELETE CASCADE
                )
                """
            )

    def get(
        self,
        job_id: str,
    ) -> JobProfile | None:
        self.ensure_table()

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT profile_json
                FROM job_profiles
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if not row:
            return None

        data = json.loads(
            row["profile_json"]
        )

        return JobProfile(**data)

    def get_or_create(
        self,
        job: Job,
    ) -> JobProfile:
        self.ensure_table()

        signature = build_job_profile_signature(
            job
        )

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    profile_json,
                    job_signature,
                    profile_version
                FROM job_profiles
                WHERE job_id = ?
                """,
                (job.id,),
            ).fetchone()

        if (
            row
            and row["job_signature"] == signature
            and row["profile_version"]
            == JOB_PROFILE_VERSION
        ):
            return JobProfile(
                **json.loads(
                    row["profile_json"]
                )
            )

        profile = self.service.create(job)

        now = utc_now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO job_profiles (
                    job_id,
                    profile_json,
                    job_signature,
                    profile_version,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    job_signature = excluded.job_signature,
                    profile_version = excluded.profile_version,
                    updated_at = excluded.updated_at
                """,
                (
                    job.id,
                    json.dumps(
                        asdict(profile),
                        ensure_ascii=False,
                    ),
                    signature,
                    JOB_PROFILE_VERSION,
                    now,
                    now,
                ),
            )

        return profile
