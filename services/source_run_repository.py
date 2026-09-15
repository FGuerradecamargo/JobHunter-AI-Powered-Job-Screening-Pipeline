from datetime import datetime, timedelta, timezone
import re
from uuid import uuid4

from services.database import get_connection


LEASE_SECONDS = 3600
ERROR_CODES = frozenset({"rate_limited", "transport_failure", "provider_setup_failed",
    "response_shape", "query_failed", "degraded_records", "lease_lost", "worker_expired"})


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    if value.tzinfo is None:
        raise ValueError("Scheduler time must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat()


class SourceRunRepository:
    def acquire(self, identity, source_type, company_source_id, now, ttl=LEASE_SECONDS):
        if not re.fullmatch(r"(?:adzuna|jooble|(?:lever|ashby):[A-Za-z0-9_-]{1,128})", identity):
            raise ValueError("Unsupported scheduler source identity.")
        if source_type not in {"adzuna", "jooble", "lever", "ashby"} or ttl <= 0:
            raise ValueError("Invalid scheduler source policy.")
        if identity != (f"{source_type}:{company_source_id}" if company_source_id else source_type):
            raise ValueError("Source identity mismatch.")
        started = timestamp(now)
        expires = timestamp(now + timedelta(seconds=ttl))
        run_id = uuid4().hex
        with get_connection() as conn:
            conn.execute("""INSERT INTO source_ingestion_state(source_identity) VALUES (?)
                            ON CONFLICT(source_identity) DO NOTHING""", (identity,))
            claimed = conn.execute("""
                UPDATE source_ingestion_state
                SET active_run_id=?, lease_expires_at=?, last_attempt_at=?
                WHERE source_identity=?
                  AND (active_run_id IS NULL OR lease_expires_at<=?)
                  AND (next_eligible_at IS NULL OR next_eligible_at<=?)
            """, (run_id, expires, started, identity, started, started)).rowcount
            if not claimed:
                row = conn.execute("SELECT * FROM source_ingestion_state WHERE source_identity=?", (identity,)).fetchone()
                reason = "skipped_claimed_elsewhere" if row["active_run_id"] and row["lease_expires_at"] > started else "skipped_not_due"
                return None, reason
            conn.execute("""UPDATE source_ingestion_runs SET status='expired', finished_at=?,
                            error_code='worker_expired', coverage_complete=0
                            WHERE source_identity=? AND status='running'""", (started, identity))
            conn.execute("""INSERT INTO source_ingestion_runs
                (id,source_identity,source_type,company_source_id,started_at,status,created_at)
                VALUES (?,?,?,?,?,'running',?)""",
                (run_id, identity, source_type, company_source_id, started, started))
        return run_id, "claimed"

    def renew(self, identity, run_id, now, ttl=LEASE_SECONDS):
        with get_connection() as conn:
            return conn.execute("""UPDATE source_ingestion_state SET lease_expires_at=?
                WHERE source_identity=? AND active_run_id=? AND lease_expires_at>?""",
                (timestamp(now + timedelta(seconds=ttl)), identity, run_id, timestamp(now))).rowcount > 0

    def finish(self, identity, run_id, now, result, coverage_complete, next_eligible_at):
        status = result.status
        error = result.error_code
        if status not in {"success", "partial", "failed"} or (error and error not in ERROR_CODES):
            raise ValueError("Invalid source-run outcome.")
        if coverage_complete and status != "success":
            raise ValueError("Only successful complete runs provide coverage.")
        end, due = timestamp(now), timestamp(next_eligible_at)
        with get_connection() as conn:
            owned = conn.execute("""UPDATE source_ingestion_state
                SET active_run_id=NULL, lease_expires_at=NULL, next_eligible_at=?,
                    last_success_at=CASE WHEN ?='success' THEN ? ELSE last_success_at END
                WHERE source_identity=? AND active_run_id=? AND lease_expires_at>?
            """, (due, status, end, identity, run_id, end)).rowcount
            if not owned:
                return False
            conn.execute("""UPDATE source_ingestion_runs SET finished_at=?, status=?,
                jobs_fetched=?, jobs_created=?, jobs_updated=?, jobs_unchanged=?, failed_queries=?,
                error_code=?, next_eligible_at=?, coverage_complete=?, duration_seconds=?
                WHERE id=? AND source_identity=? AND status='running'""",
                (end, status, result.fetched, result.created, result.updated, result.unchanged,
                 result.failed_queries, error, due, int(coverage_complete), result.duration_seconds,
                 run_id, identity))
        return True

    def list_runs(self, identity, limit=20):
        with get_connection() as conn:
            return [dict(row) for row in conn.execute("""SELECT * FROM source_ingestion_runs
                WHERE source_identity=? ORDER BY started_at DESC, id LIMIT ?""", (identity, limit)).fetchall()]
