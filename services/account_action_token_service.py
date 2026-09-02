from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import hashlib
import secrets
from uuid import uuid4

from services.database import (
    create_account_security_schema,
    get_connection,
)


class AccountActionTokenService:
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"

    _TOKEN_BYTES = 48

    _TTL_BY_PURPOSE = {
        PASSWORD_RESET: timedelta(
            minutes=30
        ),
        EMAIL_VERIFICATION: timedelta(
            hours=24
        ),
    }

    @classmethod
    def _validate_purpose(
        cls,
        purpose: str,
    ) -> str:
        normalized_purpose = str(
            purpose or ""
        ).strip()

        if (
            normalized_purpose
            not in cls._TTL_BY_PURPOSE
        ):
            raise ValueError(
                "Invalid account action "
                f"token purpose: {purpose}"
            )

        return normalized_purpose

    @staticmethod
    def hash_token(
        token: str,
    ) -> str:
        normalized_token = str(
            token or ""
        ).strip()

        if not normalized_token:
            raise ValueError(
                "Account action token "
                "cannot be empty."
            )

        return hashlib.sha256(
            normalized_token.encode(
                "utf-8"
            )
        ).hexdigest()

    @classmethod
    def issue_token(
        cls,
        user_id: str,
        purpose: str,
    ) -> str:
        normalized_user_id = str(
            user_id or ""
        ).strip()

        if not normalized_user_id:
            raise ValueError(
                "User ID is required."
            )

        normalized_purpose = (
            cls._validate_purpose(
                purpose
            )
        )

        now = datetime.now(
            timezone.utc
        )

        expires_at = (
            now
            + cls._TTL_BY_PURPOSE[
                normalized_purpose
            ]
        )

        raw_token = secrets.token_urlsafe(
            cls._TOKEN_BYTES
        )

        token_hash = cls.hash_token(
            raw_token
        )

        now_text = now.isoformat()

        with get_connection() as connection:
            create_account_security_schema(
                connection
            )

            # A newly issued token supersedes any
            # still-active token for the same
            # user and purpose.
            connection.execute(
                """
                UPDATE account_action_tokens
                SET invalidated_at = ?
                WHERE
                    user_id = ?
                    AND purpose = ?
                    AND used_at IS NULL
                    AND invalidated_at IS NULL
                """,
                (
                    now_text,
                    normalized_user_id,
                    normalized_purpose,
                ),
            )

            connection.execute(
                """
                INSERT INTO account_action_tokens (
                    id,
                    user_id,
                    purpose,
                    token_hash,
                    expires_at,
                    used_at,
                    invalidated_at,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    uuid4().hex,
                    normalized_user_id,
                    normalized_purpose,
                    token_hash,
                    expires_at.isoformat(),
                    None,
                    None,
                    now_text,
                ),
            )

        return raw_token

    @classmethod
    def is_token_active(
        cls,
        token: str,
        purpose: str,
    ) -> bool:
        """
        Check whether a token is currently usable
        without consuming it.
        """
        normalized_purpose = (
            cls._validate_purpose(
                purpose
            )
        )

        token_hash = cls.hash_token(
            token
        )

        now_text = datetime.now(
            timezone.utc
        ).isoformat()

        with get_connection() as connection:
            create_account_security_schema(
                connection
            )

            row = connection.execute(
                """
                SELECT 1
                FROM account_action_tokens
                WHERE
                    token_hash = ?
                    AND purpose = ?
                    AND used_at IS NULL
                    AND invalidated_at IS NULL
                    AND expires_at > ?
                LIMIT 1
                """,
                (
                    token_hash,
                    normalized_purpose,
                    now_text,
                ),
            ).fetchone()

        return row is not None

    @classmethod
    def consume_token_with_connection(
        cls,
        connection,
        token: str,
        purpose: str,
    ) -> str | None:
        """
        Atomically consume one valid token using the
        caller's transaction.
        """
        normalized_purpose = (
            cls._validate_purpose(
                purpose
            )
        )

        token_hash = cls.hash_token(
            token
        )

        now_text = datetime.now(
            timezone.utc
        ).isoformat()

        create_account_security_schema(
            connection
        )

        cursor = connection.execute(
            """
            UPDATE account_action_tokens
            SET used_at = ?
            WHERE
                token_hash = ?
                AND purpose = ?
                AND used_at IS NULL
                AND invalidated_at IS NULL
                AND expires_at > ?
            """,
            (
                now_text,
                token_hash,
                normalized_purpose,
                now_text,
            ),
        )

        if cursor.rowcount != 1:
            return None

        row = connection.execute(
            """
            SELECT user_id
            FROM account_action_tokens
            WHERE token_hash = ?
            """,
            (
                token_hash,
            ),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                "Consumed account action token "
                "could not be reloaded."
            )

        return str(
            row["user_id"]
        )

    @classmethod
    def consume_token(
        cls,
        token: str,
        purpose: str,
    ) -> str | None:
        """
        Consume one valid token in its own transaction.
        """
        with get_connection() as connection:
            return (
                cls.consume_token_with_connection(
                    connection,
                    token,
                    purpose,
                )
            )
