from __future__ import annotations

from datetime import datetime, timezone
from contextlib import nullcontext
from dataclasses import asdict, fields, replace
import hashlib
import json

from services.database import get_connection, is_postgres, upsert_raw_job, utc_now
from services.job_observation import is_personal_source, normalize_observation


class JobSourceRepository:
    def record_observation(self, job, source_type, *, user_id=None, trusted_public=False):
        """Atomically resolve identity, persist scoped evidence and project authority.

        A public source's namespace tie-break is deterministic, not a quality claim.
        Private observations may reference public identity but never replace its data.
        """
        observation = normalize_observation(job, source_type)
        source_type, job = observation.source_type, observation.job
        if (user_id is not None and not str(user_id).strip()) or (is_personal_source(source_type) and user_id is None):
            raise ValueError("Personal observations require an owner.")
        if user_id is None and trusted_public is not True:
            raise ValueError("Public observations require explicit source eligibility.")
        identity = [job.url, *(" ".join((v or "").split()).casefold()
                               for v in (job.title, job.company, job.location))]
        observation_id = hashlib.sha256(json.dumps(
            [user_id, source_type, job.id, identity], ensure_ascii=True).encode()).hexdigest()
        with get_connection() as connection:
            if is_postgres():
                connection.execute("SELECT pg_advisory_xact_lock(731304)")
            else:
                connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute("SELECT job_id FROM job_observations WHERE observation_id = ?",
                                          (observation_id,)).fetchone()
            job_id = previous["job_id"] if previous else self._resolve_identity(connection, job, user_id, observation_id)
            from models.job import Job
            payload = {field.name: getattr(job, field.name) for field in fields(Job)}
            payload["id"] = job_id
            published = getattr(job, "published_at", None)
            if isinstance(published, datetime):
                payload["published_at"] = published.isoformat()
            status = upsert_raw_job(replace(job, id=job_id), _connection=connection)
            now = utc_now()
            connection.execute("""INSERT INTO job_observations
                (observation_id, job_id, user_id, source_type, external_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(observation_id) DO UPDATE SET
                    payload_json = excluded.payload_json, updated_at = excluded.updated_at
            """, (observation_id, job_id, user_id, source_type, observation.external_id,
                  json.dumps(payload, ensure_ascii=True), now, now))
            self.add_source(job_id, source_type, user_id, connection=connection)
            if status == "created":
                connection.execute("INSERT INTO job_content_authority (job_id, observation_id) VALUES (?, ?)",
                                   (job_id, observation_id))
            authority = connection.execute("""SELECT o.user_id, o.observation_id FROM job_content_authority a
                JOIN job_observations o ON o.observation_id = a.observation_id WHERE a.job_id = ?""", (job_id,)).fetchone()
            # A fresh eligible public observation can establish authority after exact
            # identity resolution. Migration alone never confers that authority.
            if authority is None and user_id is None:
                connection.execute("INSERT INTO job_content_authority (job_id, observation_id) VALUES (?, ?)",
                                   (job_id, observation_id))
                authority = {"user_id": None, "observation_id": observation_id}
            if authority and user_id is None and authority["user_id"] is None:
                chosen = connection.execute("""SELECT observation_id, payload_json FROM job_observations
                    WHERE job_id = ? AND user_id IS NULL
                    ORDER BY CASE WHEN source_type = 'job_page' THEN 0 ELSE 1 END,
                        source_type, external_id, observation_id LIMIT 1""", (job_id,)).fetchone()
                changed = self._apply_authorized_content(connection, job_id, json.loads(chosen["payload_json"]), now)
                connection.execute("UPDATE job_content_authority SET observation_id = ? WHERE job_id = ?",
                                   (chosen["observation_id"], job_id))
                if changed and status != "created":
                    status = "updated"
            elif authority and user_id is not None and authority["observation_id"] == observation_id:
                shared = connection.execute("SELECT 1 FROM job_sources WHERE job_id = ? AND (user_id IS NULL OR user_id <> ?)",
                                            (job_id, user_id)).fetchone()
                if not shared and self._apply_authorized_content(connection, job_id, payload, now) and status != "created":
                    status = "updated"
            if user_id is None:
                connection.execute("UPDATE jobs SET archived_at = NULL WHERE id = ? AND archived_at IS NOT NULL", (job_id,))
            return job_id, status

    @staticmethod
    def _resolve_identity(connection, job, user_id, observation_id):
        if job.url and job.company and job.location:
            rows = connection.execute("""SELECT j.id FROM jobs j WHERE j.url = ?
                AND LOWER(TRIM(j.title)) = LOWER(TRIM(?)) AND LOWER(TRIM(j.company)) = LOWER(TRIM(?))
                AND LOWER(TRIM(j.location)) = LOWER(TRIM(?))
                AND EXISTS (SELECT 1 FROM job_sources s WHERE s.job_id = j.id AND s.user_id IS NULL)
                LIMIT 2""", (job.url, job.title, job.company, job.location)).fetchall()
            if len(rows) == 1:
                return rows[0]["id"]
        if user_id is not None:
            return "private:" + observation_id
        existing = connection.execute("SELECT id FROM jobs WHERE id = ?", (job.id,)).fetchone()
        # An ID collision without matching public identity is not a deduplication.
        return "public:" + observation_id if existing else job.id

    @staticmethod
    def _apply_authorized_content(connection, job_id, payload, now):
        fields = ("raw_text", "description", "title", "company", "location", "url", "remote", "salary", "easy_apply")
        current = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        values = tuple((int(payload[f]) if payload.get(f) is not None else None)
                       if f in {"remote", "easy_apply"} else payload.get(f) for f in fields)
        if all(current[f] == value for f, value in zip(fields, values)):
            return False
        from services.job_category_service import JobCategoryService
        category = JobCategoryService().classify(title=payload.get("title") or "",
            description=payload.get("description") or "", raw_text=payload.get("raw_text") or "")
        connection.execute("""UPDATE jobs SET raw_text = ?, description = ?, title = ?, company = ?,
            location = ?, url = ?, remote = ?, salary = ?, easy_apply = ?, category = ?, sub_category = ?, updated_at = ?
            WHERE id = ?""", (*values, category.category, category.sub_category, now, job_id))
        return True

    def list_observations_for_user(self, user_id):
        if not user_id or not str(user_id).strip():
            raise ValueError("Observation owner is required.")
        with get_connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM job_observations WHERE user_id = ? ORDER BY observation_id", (user_id,)).fetchall()]

    def list_public_market_rows(self):
        """Public provider evidence eligible for global Market projection.

        Candidate/private observations are excluded at the repository boundary.
        A discovery signal supplies only the public search taxonomy that led to
        the vacancy; it is not candidate evidence.
        """
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    o.observation_id,
                    o.job_id,
                    o.source_type,
                    o.external_id,
                    o.payload_json,
                    o.created_at,
                    o.updated_at,
                    d.category,
                    d.sub_category,
                    d.search_query,
                    d.last_seen_at
                FROM job_observations o
                JOIN jobs j
                  ON j.id = o.job_id
                 AND j.archived_at IS NULL
                JOIN job_discovery_signals d
                  ON d.job_id = o.job_id
                 AND d.source_type = o.source_type
                WHERE o.user_id IS NULL
                ORDER BY
                    o.job_id,
                    o.source_type,
                    o.external_id,
                    d.sub_category,
                    d.search_query
                """
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def record_fetched_description(self, job):
        """Only an independently public canonical URL may enrich shared data.

        This internal boundary is used after the existing public-page fetch, not
        for Gmail or manual submissions. Other incoming fields are never copied.
        """
        from models.job import Job
        with get_connection() as connection:
            row = connection.execute("""SELECT o.payload_json FROM job_content_authority a
                JOIN job_observations o ON o.observation_id = a.observation_id
                WHERE a.job_id = ? AND o.user_id IS NULL""", (job.id,)).fetchone()
        if row is None or not job.description:
            return False
        payload = json.loads(row["payload_json"])
        canonical = Job(**{field.name: payload[field.name] for field in fields(Job) if field.name in payload})
        if not canonical.url or canonical.url != job.url:
            return False
        self.record_observation(replace(canonical, description=job.description), "job_page", trusted_public=True)
        return True

    def load_job_hard_facts(self, job_id, *, user_id=None, candidate_id=None):
        """Read literal authorized observation fields, not AI-extracted requirements."""
        from models.profile_interpretation import HardJobFact, JobHardFacts
        with get_connection() as connection:
            row = connection.execute("""SELECT o.observation_id, o.payload_json FROM job_content_authority a
                JOIN job_observations o ON o.observation_id = a.observation_id
                WHERE a.job_id = ? AND (o.user_id IS NULL OR o.user_id = ? OR EXISTS (
                    SELECT 1 FROM users u WHERE u.id = o.user_id AND u.candidate_id = ?
                ))""", (job_id, user_id, candidate_id)).fetchone()
        if row is None:
            raise ValueError("Authorized job observation is unavailable.")
        payload = json.loads(row["payload_json"])
        facts = []
        for kind in ("title", "company", "location", "url", "description", "raw_text", "salary", "remote"):
            value = payload.get(kind)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            value = str(value)
            ref = f"job-observation:{row['observation_id']}:{kind}"
            facts.append(HardJobFact(fact_id=ref, kind=kind, value=value, source_ref=ref))
        signature = hashlib.sha256(json.dumps([asdict(fact) for fact in facts],
            sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        return JobHardFacts(job_id, signature, tuple(facts))

    def add_source(
        self,
        job_id: str,
        source_type: str,
        user_id: str | None = None,
        *,
        connection=None,
    ) -> None:
        source_type = str(source_type or "").strip().lower()
        if not source_type or (user_id is not None and not str(user_id).strip()):
            raise ValueError("Source scope is invalid.")
        if is_personal_source(source_type) and user_id is None:
            raise ValueError("Personal sources require a user.")
        seen_at = (
            datetime.now(timezone.utc).isoformat()
        )

        with (nullcontext(connection) if connection is not None else get_connection()) as connection:
            if user_id is None:
                connection.execute(
                    """
                    INSERT INTO job_sources (
                        job_id,
                        user_id,
                        source_type,
                        discovered_at,
                        last_seen_at
                    )
                    VALUES (
                        ?,
                        NULL,
                        ?,
                        ?,
                        ?
                    )
                    ON CONFLICT (
                        job_id,
                        source_type
                    )
                    WHERE user_id IS NULL
                    DO UPDATE SET
                        last_seen_at = EXCLUDED.last_seen_at
                    """,
                    (
                        job_id,
                        source_type,
                        seen_at,
                        seen_at,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO job_sources (
                        job_id,
                        user_id,
                        source_type,
                        discovered_at,
                        last_seen_at
                    )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    ON CONFLICT (
                        job_id,
                        user_id,
                        source_type
                    )
                    WHERE user_id IS NOT NULL
                    DO UPDATE SET
                        last_seen_at = EXCLUDED.last_seen_at
                    """,
                    (
                        job_id,
                        user_id,
                        source_type,
                        seen_at,
                        seen_at,
                    ),
                )

    def add_discovery_signal(
        self,
        job_id: str,
        source_type: str,
        category: str,
        sub_category: str,
        search_query: str,
    ) -> None:
        """
        Persist global evidence describing how a job
        was discovered.

        Rediscovering the same signal updates only
        last_seen_at. A job may keep multiple signals
        from different searches or taxonomies.
        """
        seen_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        normalized_job_id = str(
            job_id or ""
        ).strip()

        normalized_source_type = str(
            source_type or ""
        ).strip()

        normalized_category = str(
            category or ""
        ).strip()

        normalized_sub_category = str(
            sub_category or ""
        ).strip()

        normalized_search_query = str(
            search_query or ""
        ).strip()

        if not all(
            (
                normalized_job_id,
                normalized_source_type,
                normalized_category,
                normalized_sub_category,
                normalized_search_query,
            )
        ):
            raise ValueError(
                "Discovery signal fields must be non-empty."
            )

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO job_discovery_signals (
                    job_id,
                    source_type,
                    category,
                    sub_category,
                    search_query,
                    first_seen_at,
                    last_seen_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )

                ON CONFLICT (
                    job_id,
                    source_type,
                    category,
                    sub_category,
                    search_query
                )
                DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at
                """,
                (
                    normalized_job_id,
                    normalized_source_type,
                    normalized_category,
                    normalized_sub_category,
                    normalized_search_query,
                    seen_at,
                    seen_at,
                ),
            )


    def list_by_user(
        self,
        user_id: str,
    ) -> list[str]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT job_id
                FROM job_sources
                WHERE user_id = ?
                ORDER BY discovered_at DESC
                """,
                (user_id,),
            ).fetchall()

        return [
            row["job_id"]
            for row in rows
        ]

    def list_sources_for_job(
        self,
        job_id: str,
        user_id: str | None = None,
    ):
        with get_connection() as connection:
            return connection.execute(
                """
                SELECT
                    user_id,
                    source_type,
                    discovered_at,
                    last_seen_at
                FROM job_sources
                WHERE job_id = ?
                    AND (user_id IS NULL OR user_id = ?)
                ORDER BY discovered_at ASC
                """,
                (job_id, user_id),
            ).fetchall()
