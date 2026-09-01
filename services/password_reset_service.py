from __future__ import annotations

from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.auth_service import AuthService
from services.database import (
    create_account_security_schema,
    get_connection,
    utc_now,
)
from services.session_store import (
    revoke_user_sessions_with_connection,
)


class PasswordResetService:

    @staticmethod
    def request_reset_token(
        email: str,
    ) -> str | None:
        """
        Return a raw reset token only for an account
        that exists and has a local password.

        Callers must never expose whether None or a
        token was returned. The public response must
        always remain generic.
        """
        normalized_email = str(
            email or ""
        ).strip().lower()

        if not normalized_email:
            return None

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    password_hash
                FROM users
                WHERE email = ?
                """,
                (
                    normalized_email,
                ),
            ).fetchone()

        if (
            row is None
            or not row["password_hash"]
        ):
            return None

        return (
            AccountActionTokenService
            .issue_token(
                user_id=str(
                    row["id"]
                ),
                purpose=(
                    AccountActionTokenService
                    .PASSWORD_RESET
                ),
            )
        )

    @staticmethod
    def reset_password(
        token: str,
        new_password: str,
    ) -> bool:
        """
        Consume the reset token, replace the password
        and revoke all sessions atomically.
        """
        # Validate and hash before consuming the token.
        # A rejected password must not burn a valid
        # recovery token.
        password_hash = (
            AuthService.hash_password(
                new_password
            )
        )

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
                        .PASSWORD_RESET
                    ),
                )
            )

            if user_id is None:
                return False

            cursor = connection.execute(
                """
                UPDATE users
                SET
                    password_hash = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    password_hash,
                    now,
                    user_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Password reset user "
                    "could not be updated."
                )

            revoke_user_sessions_with_connection(
                connection,
                user_id,
            )

            # Defensive cleanup: no other active reset
            # token should survive a successful reset.
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
                        .PASSWORD_RESET
                    ),
                ),
            )

        return True
