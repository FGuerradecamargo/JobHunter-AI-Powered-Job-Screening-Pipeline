"""Transactional separation of private observations and public canonical content."""
from dataclasses import fields, replace
import hashlib
import json

from models.job import Job
from services.database import get_connection, is_postgres, upsert_raw_job, utc_now
from services.job_observation import normalize_observation, is_personal_source
from services.job_source_repository import JobSourceRepository


def _digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True).encode()).hexdigest()


class JobObservationRepository:
    def __init__(self, source_repository=None):
        self.sources = source_repository or JobSourceRepository()

    def record(self, job, source_type, *, user_id=None, trusted_public=False):
        observed = normalize_observation(job, source_type)
        source_type, job = observed.source_type, observed.job
        if (user_id is not None and not str(user_id).strip()) or (is_personal_source(source_type) and user_id is None):
            raise ValueError("Personal observations require an owner.")
        if user_id is None and trusted_public is not True:
            raise ValueError("Public observations require explicit source authority.")
        observation_id = _digest([user_id, source_type, job.id, job.url])
        with get_connection() as conn:
            # Serialize only the short identity/provenance write, never provider work.
            if is_postgres():
                conn.execute("SELECT pg_advisory_xact_lock(731304)")
            else:
                conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute("SELECT job_id FROM job_observations WHERE observation_id = ?",
                                    (observation_id,)).fetchone()
            canonical_id = previous["job_id"] if previous else self._resolve(conn, job, user_id, observation_id)
            stored_job = replace(job, id=canonical_id)
            payload = {field.name: getattr(stored_job, field.name) for field in fields(Job)}
            status = upsert_raw_job(stored_job, _connection=conn)
            now = utc_now()
            conn.execute("""
                INSERT INTO job_observations
                    (observation_id, job_id, user_id, source_type, external_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(observation_id) DO UPDATE SET
                    payload_json = excluded.payload_json, updated_at = excluded.updated_at
            """, (observation_id, canonical_id, user_id, source_type, observed.external_id,
                  json.dumps(payload, ensure_ascii=True), now, now))
            self.sources.add_source(canonical_id, source_type, user_id, connection=conn)
            if status == "created":
                conn.execute("INSERT INTO job_content_authority (job_id, observation_id) VALUES (?, ?)",
                             (canonical_id, observation_id))
            authority = conn.execute("""
                SELECT o.user_id, o.observation_id FROM job_content_authority a
                JOIN job_observations o ON o.observation_id = a.observation_id WHERE a.job_id = ?
            """, (canonical_id,)).fetchone()
            # No authority row means legacy data: freeze, never infer trust from an ID.
            if authority and user_id is None and authority["user_id"] is None:
                chosen = conn.execute("""
                    SELECT observation_id, payload_json FROM job_observations
                    WHERE job_id = ? AND user_id IS NULL
                    ORDER BY source_type, external_id, observation_id LIMIT 1
                """, (canonical_id,)).fetchone()
                if self._apply(conn, canonical_id, json.loads(chosen["payload_json"]), now) and status != "created":
                    status = "updated"
                conn.execute("UPDATE job_content_authority SET observation_id = ? WHERE job_id = ?",
                             (chosen["observation_id"], canonical_id))
            elif authority and authority["observation_id"] == observation_id and user_id is not None:
                # Private projection can only change while exclusively owned by its creator.
                shared = conn.execute("SELECT 1 FROM job_sources WHERE job_id = ? AND (user_id IS NULL OR user_id <> ?)",
                                      (canonical_id, user_id)).fetchone()
                if not shared and self._apply(conn, canonical_id, payload, now) and status != "created":
                    status = "updated"
            if user_id is None:
                conn.execute("UPDATE jobs SET archived_at = NULL WHERE id = ? AND archived_at IS NOT NULL", (canonical_id,))
            return canonical_id, status

    @staticmethod
    def _resolve(conn, job, user_id, observation_id):
        if job.url and job.company and job.location:
            matches = conn.execute("""
                SELECT j.id FROM jobs j
                WHERE j.url = ? AND LOWER(TRIM(j.title)) = LOWER(TRIM(?))
                    AND LOWER(TRIM(j.company)) = LOWER(TRIM(?))
                    AND LOWER(TRIM(j.location)) = LOWER(TRIM(?))
                    AND EXISTS (SELECT 1 FROM job_sources s WHERE s.job_id = j.id AND s.user_id IS NULL)
                LIMIT 2
            """, (job.url, job.title, job.company, job.location)).fetchall()
            if len(matches) == 1:
                return matches[0]["id"]
        if user_id is not None:
            return "private:" + observation_id
        existing = conn.execute("SELECT url FROM jobs WHERE id = ?", (job.id,)).fetchone()
        if existing:
            private = conn.execute("SELECT 1 FROM job_sources WHERE job_id = ? AND user_id IS NOT NULL", (job.id,)).fetchone()
            public = conn.execute("SELECT 1 FROM job_sources WHERE job_id = ? AND user_id IS NULL", (job.id,)).fetchone()
            if private and not public:
                raise ValueError("Global import cannot promote a personal record.")
            if not public:
                return "public:" + observation_id
            if existing["url"] != job.url:
                return "public:" + observation_id
        return job.id

    @staticmethod
    def _apply(conn, job_id, payload, now):
        fields = ("raw_text", "description", "title", "company", "location", "url", "remote", "salary", "easy_apply")
        current = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        # A provider omitting a description must not erase already fetched public data.
        if payload.get("description") is None:
            payload = {**payload, "description": current["description"]}
        values = tuple((int(payload[f]) if payload.get(f) is not None else None)
                       if f in {"remote", "easy_apply"} else payload.get(f) for f in fields)
        if all(current[f] == value for f, value in zip(fields, values)):
            return False
        from services.job_category_service import JobCategoryService
        category = JobCategoryService().classify(title=payload.get("title") or "",
            description=payload.get("description") or "", raw_text=payload.get("raw_text") or "")
        conn.execute("""UPDATE jobs SET raw_text = ?, description = ?, title = ?, company = ?,
            location = ?, url = ?, remote = ?, salary = ?, easy_apply = ?, category = ?, sub_category = ?, updated_at = ?
            WHERE id = ?""", (*values, category.category, category.sub_category, now, job_id))
        return True

    def list_for_user(self, user_id):
        if not user_id or not str(user_id).strip():
            raise ValueError("Observation owner is required.")
        with get_connection() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM job_observations WHERE user_id = ? ORDER BY observation_id", (user_id,),
            ).fetchall()]
