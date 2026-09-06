from __future__ import annotations

from uuid import uuid4

from services.database import (
    create_user_identity_schema,
    get_connection,
    utc_now,
)


class UserIdentityRepository:
    @staticmethod
    def _normalize_provider(
        provider: str,
    ) -> str:
        normalized = str(
            provider or ""
        ).strip().lower()

        if not normalized:
            raise ValueError(
                "Identity provider is required."
            )

        return normalized

    @staticmethod
    def _normalize_subject(
        subject: str,
    ) -> str:
        normalized = str(
            subject or ""
        ).strip()

        if not normalized:
            raise ValueError(
                "Identity subject is required."
            )

        return normalized

    def get_user_id(
        self,
        *,
        provider: str,
        subject: str,
    ) -> str | None:
        normalized_provider = (
            self._normalize_provider(
                provider
            )
        )
        normalized_subject = (
            self._normalize_subject(
                subject
            )
        )

        with get_connection() as connection:
            create_user_identity_schema(
                connection
            )

            row = connection.execute(
                """
                SELECT user_id
                FROM user_identities
                WHERE
                    provider = ?
                    AND subject = ?
                """,
                (
                    normalized_provider,
                    normalized_subject,
                ),
            ).fetchone()

        if row is None:
            return None

        return str(
            row["user_id"]
        )

    def link(
        self,
        *,
        user_id: str,
        provider: str,
        subject: str,
        provider_email: str | None = None,
    ) -> None:
        normalized_user_id = str(
            user_id or ""
        ).strip()

        if not normalized_user_id:
            raise ValueError(
                "User ID is required."
            )

        normalized_provider = (
            self._normalize_provider(
                provider
            )
        )
        normalized_subject = (
            self._normalize_subject(
                subject
            )
        )

        normalized_email = str(
            provider_email or ""
        ).strip().lower() or None

        now = utc_now()

        with get_connection() as connection:
            create_user_identity_schema(
                connection
            )

            connection.execute(
                """
                INSERT INTO user_identities (
                    id,
                    user_id,
                    provider,
                    subject,
                    provider_email,
                    created_at,
                    updated_at,
                    last_authenticated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    normalized_user_id,
                    normalized_provider,
                    normalized_subject,
                    normalized_email,
                    now,
                    now,
                    now,
                ),
            )

    def record_authentication(
        self,
        *,
        provider: str,
        subject: str,
        provider_email: str | None = None,
    ) -> str | None:
        normalized_provider = (
            self._normalize_provider(
                provider
            )
        )
        normalized_subject = (
            self._normalize_subject(
                subject
            )
        )

        normalized_email = str(
            provider_email or ""
        ).strip().lower() or None

        now = utc_now()

        with get_connection() as connection:
            create_user_identity_schema(
                connection
            )

            row = connection.execute(
                """
                SELECT user_id
                FROM user_identities
                WHERE
                    provider = ?
                    AND subject = ?
                """,
                (
                    normalized_provider,
                    normalized_subject,
                ),
            ).fetchone()

            if row is None:
                return None

            connection.execute(
                """
                UPDATE user_identities
                SET
                    provider_email = ?,
                    updated_at = ?,
                    last_authenticated_at = ?
                WHERE
                    provider = ?
                    AND subject = ?
                """,
                (
                    normalized_email,
                    now,
                    now,
                    normalized_provider,
                    normalized_subject,
                ),
            )

        return str(
            row["user_id"]
        )
