from __future__ import annotations

from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.database import (
    create_account_security_schema,
    get_connection,
    utc_now,
)


class EmailVerificationService:
    @classmethod
    def is_email_verified(
        cls,
        user_id: str,
    ) -> bool:
        normalized_user_id = str(
            user_id or ""
        ).strip()

        if not normalized_user_id:
            raise ValueError(
                "User ID is required."
            )

        with get_connection() as connection:
            create_account_security_schema(
                connection
            )

            row = connection.execute(
                """
                SELECT email_verified_at
                FROM users
                WHERE id = ?
                """,
                (
                    normalized_user_id,
                ),
            ).fetchone()

        if row is None:
            raise ValueError(
                "User not found."
            )

        return bool(
            row["email_verified_at"]
        )

    @classmethod
    def issue_verification_token(
        cls,
        user_id: str,
    ) -> str | None:
        normalized_user_id = str(
            user_id or ""
        ).strip()

        if not normalized_user_id:
            raise ValueError(
                "User ID is required."
            )

        with get_connection() as connection:
            create_account_security_schema(
                connection
            )

            row = connection.execute(
                """
                SELECT
                    id,
                    email_verified_at
                FROM users
                WHERE id = ?
                """,
                (
                    normalized_user_id,
                ),
            ).fetchone()

        if row is None:
            raise ValueError(
                "User not found."
            )

        if row["email_verified_at"]:
            return None

        return (
            AccountActionTokenService
            .issue_token(
                user_id=normalized_user_id,
                purpose=(
                    AccountActionTokenService
                    .EMAIL_VERIFICATION
                ),
            )
        )

    @classmethod
    def verify_email(
        cls,
        token: str,
    ) -> bool:
        now = utc_now()

        with get_connection() as connection:
            create_account_security_schema(
                connection
            )

            user_id = (
                AccountActionTokenService
                .consume_token_with_connection(
                    connection,
                    token,
                    (
                        AccountActionTokenService
                        .EMAIL_VERIFICATION
                    ),
                )
            )

            if user_id is None:
                return False

            cursor = connection.execute(
                """
                UPDATE users
                SET
                    email_verified_at = COALESCE(
                        email_verified_at,
                        ?
                    ),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    now,
                    user_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Verification token user "
                    "could not be updated."
                )

            # Defensive cleanup. A successful
            # verification makes any remaining
            # verification token unnecessary.
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
                    now,
                    user_id,
                    (
                        AccountActionTokenService
                        .EMAIL_VERIFICATION
                    ),
                ),
            )

        return True
