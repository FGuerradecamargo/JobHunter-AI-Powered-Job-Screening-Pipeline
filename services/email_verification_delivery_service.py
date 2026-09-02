from __future__ import annotations

from html import escape
import logging

from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.database import (
    create_account_security_schema,
    get_connection,
)
from services.email_verification_service import (
    EmailVerificationService,
)
from services.public_url_service import (
    PublicUrlConfigurationError,
    PublicUrlService,
)
from services.transactional_email_service import (
    TransactionalEmailError,
    TransactionalEmailService,
)


logger = logging.getLogger(__name__)


class EmailVerificationDeliveryService:
    @classmethod
    def send_verification_email(
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
                SELECT
                    email,
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
            return False

        recipient_email = str(
            row["email"]
        ).strip()

        token = (
            EmailVerificationService
            .issue_verification_token(
                normalized_user_id
            )
        )

        if token is None:
            return False

        try:
            verification_url = (
                PublicUrlService
                .email_verification_url(
                    token
                )
            )

        except PublicUrlConfigurationError:
            logger.exception(
                "Email verification public URL "
                "could not be generated."
            )
            return False

        safe_verification_url = escape(
            verification_url,
            quote=True,
        )

        token_hash = (
            AccountActionTokenService
            .hash_token(token)
        )

        try:
            TransactionalEmailService.send_email(
                to_email=recipient_email,
                subject=(
                    "Verify your WorkPilot email"
                ),
                html=(
                    "<p>Welcome to WorkPilot.</p>"
                    "<p>Please verify your email "
                    "address to confirm that it "
                    "belongs to you.</p>"
                    "<p>"
                    f'<a href="{safe_verification_url}">'
                    "Verify your email"
                    "</a>"
                    "</p>"
                    "<p>This link expires in "
                    "24 hours and can only "
                    "be used once.</p>"
                    "<p>If you did not create "
                    "this account, you can ignore "
                    "this email.</p>"
                ),
                idempotency_key=(
                    "email-verification-"
                    f"{token_hash}"
                ),
            )

        except TransactionalEmailError:
            logger.exception(
                "Email verification delivery "
                "failed."
            )
            return False

        return True
