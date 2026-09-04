from __future__ import annotations

from html import escape
import logging

from services.account_action_rate_limiter import (
    AccountActionRateLimiter,
)
from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.password_reset_service import (
    PasswordResetService,
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


class AccountRecoveryService:
    GENERIC_RESET_RESPONSE = (
        "If an account exists for that email, "
        "password reset instructions will be sent."
    )

    @classmethod
    def request_password_reset(
        cls,
        email: str,
    ) -> str:
        """
        Public password-reset request boundary.

        The returned response never reveals whether
        an account exists, has a local password,
        whether URL configuration is available, or
        whether email delivery succeeded.
        """
        allowed = (
            AccountActionRateLimiter.consume(
                "password_reset_request",
                email,
            )
        )

        if not allowed:
            return cls.GENERIC_RESET_RESPONSE

        token = (
            PasswordResetService
            .request_reset_token(
                email
            )
        )

        if token is None:
            return cls.GENERIC_RESET_RESPONSE

        try:
            reset_url = (
                PublicUrlService
                .password_reset_url(
                    token
                )
            )

        except PublicUrlConfigurationError:
            logger.exception(
                "Password reset public URL "
                "could not be generated."
            )

            return cls.GENERIC_RESET_RESPONSE

        safe_reset_url = escape(
            reset_url,
            quote=True,
        )

        token_hash = (
            AccountActionTokenService
            .hash_token(token)
        )

        try:
            TransactionalEmailService.send_email(
                to_email=email,
                subject=(
                    "Reset your WorkPilot password"
                ),
                html=(
                    "<p>We received a request to "
                    "reset your WorkPilot password."
                    "</p>"
                    "<p>"
                    f'<a href="{safe_reset_url}">'
                    "Reset your password"
                    "</a>"
                    "</p>"
                    "<p>This link expires in "
                    "30 minutes and can only "
                    "be used once.</p>"
                    "<p>If you did not request "
                    "this, you can ignore this "
                    "email.</p>"
                ),
                idempotency_key=(
                    "password-reset-"
                    f"{token_hash}"
                ),
            )

        except TransactionalEmailError:
            # Never expose account existence or
            # provider status through the public
            # recovery response.
            logger.exception(
                "Password reset email delivery "
                "failed."
            )

        return cls.GENERIC_RESET_RESPONSE
