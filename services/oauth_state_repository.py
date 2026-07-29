from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from services.database import get_connection
from dataclasses import dataclass


@dataclass(frozen=True)
class OAuthAuthorizationState:
    user_id: str
    code_verifier: str


class OAuthStateRepository:
    STATE_LIFETIME_MINUTES = 15

    def save(
            self,
            state: str,
            user_id: str,
            code_verifier: str,
    ) -> None:
        if not state:
            raise ValueError("OAuth state is required.")

        if not user_id:
            raise ValueError("User ID is required.")

        if not code_verifier:
            raise ValueError(
                "OAuth code verifier is required."
            )

        now = datetime.now(timezone.utc).isoformat()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO oauth_authorization_states (
                    state,
                    user_id,
                    code_verifier,
                    created_at,
                    consumed_at
                )
                VALUES (?, ?, ?, ?, NULL)
                """,
                (
                    state,
                    user_id,
                    code_verifier,
                    now,
                ),
            )

    def consume(
            self,
            state: str,
    ) -> Optional[OAuthAuthorizationState]:

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    state,
                    code_verifier,
                    user_id,
                    created_at,
                    consumed_at
                FROM oauth_authorization_states
                WHERE state = ?
                """,
                (state,),
            ).fetchone()

            if row is None:
                return None

            if row["consumed_at"] is not None:
                return None

            created_at = datetime.fromisoformat(
                row["created_at"]
            )

            expires_at = created_at + timedelta(
                minutes=self.STATE_LIFETIME_MINUTES
            )

            now = datetime.now(timezone.utc)

            if now > expires_at:
                return None

            connection.execute(
                """
                UPDATE oauth_authorization_states
                SET consumed_at = ?
                WHERE state = ?
                """,
                (
                    now.isoformat(),
                    state,
                ),
            )

        return OAuthAuthorizationState(
            user_id=row["user_id"],
            code_verifier=row["code_verifier"],
        )

    def delete_expired(self) -> int:
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(
                minutes=self.STATE_LIFETIME_MINUTES
            )
        ).isoformat()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM oauth_authorization_states
                WHERE
                    created_at < ?
                    OR consumed_at IS NOT NULL
                """,
                (cutoff,),
            )

        return cursor.rowcount