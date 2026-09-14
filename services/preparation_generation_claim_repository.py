from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.database import get_connection


class PreparationGenerationClaimRepository:
    def acquire(
        self,
        *,
        candidate_id: str,
        job_id: str,
        application_context_signature: str,
        claim_token: str,
        ttl_seconds: int,
    ) -> bool:
        candidate_id = str(candidate_id or "").strip()
        job_id = str(job_id or "").strip()
        signature = str(application_context_signature or "").strip()
        claim_token = str(claim_token or "").strip()
        if not candidate_id or not job_id or not signature or not claim_token:
            raise ValueError("Preparation generation claim scope is incomplete.")
        if ttl_seconds <= 0:
            raise ValueError("Preparation generation claim TTL must be positive.")

        now = datetime.now(timezone.utc)
        claimed_at = now.isoformat()
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO candidate_preparation_generation_claims (
                    candidate_id, job_id, application_context_signature,
                    claim_token, claimed_at, claim_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    candidate_id, job_id, application_context_signature
                ) DO UPDATE SET
                    claim_token = excluded.claim_token,
                    claimed_at = excluded.claimed_at,
                    claim_expires_at = excluded.claim_expires_at
                WHERE
                    candidate_preparation_generation_claims.claim_expires_at
                        <= excluded.claimed_at
                    OR candidate_preparation_generation_claims.claim_token
                        = excluded.claim_token
                """,
                (
                    candidate_id,
                    job_id,
                    signature,
                    claim_token,
                    claimed_at,
                    expires_at,
                ),
            )
        return cursor.rowcount > 0

    def release(
        self,
        *,
        candidate_id: str,
        job_id: str,
        application_context_signature: str,
        claim_token: str,
    ) -> bool:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM candidate_preparation_generation_claims
                WHERE candidate_id = ?
                    AND job_id = ?
                    AND application_context_signature = ?
                    AND claim_token = ?
                """,
                (
                    str(candidate_id or "").strip(),
                    str(job_id or "").strip(),
                    str(application_context_signature or "").strip(),
                    str(claim_token or "").strip(),
                ),
            )
        return cursor.rowcount > 0
