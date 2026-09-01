from __future__ import annotations

import os
from urllib.parse import urlencode
from urllib.parse import urlparse


class PublicUrlConfigurationError(
    RuntimeError
):
    pass


class PublicUrlService:
    _BASE_URL_ENV = (
        "WORKPILOT_PUBLIC_BASE_URL"
    )

    @classmethod
    def _base_url(
        cls,
    ) -> str:
        value = str(
            os.getenv(
                cls._BASE_URL_ENV
            )
            or ""
        ).strip().rstrip("/")

        if not value:
            raise PublicUrlConfigurationError(
                "WorkPilot public URL "
                "is not configured."
            )

        parsed = urlparse(
            value
        )

        if (
            parsed.scheme
            not in {
                "http",
                "https",
            }
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise PublicUrlConfigurationError(
                "WorkPilot public URL "
                "configuration is invalid."
            )

        # Plain HTTP is acceptable only for
        # local development.
        if (
            parsed.scheme == "http"
            and parsed.hostname
            not in {
                "localhost",
                "127.0.0.1",
                "::1",
            }
        ):
            raise PublicUrlConfigurationError(
                "WorkPilot public URL "
                "must use HTTPS."
            )

        return value

    @classmethod
    def password_reset_url(
        cls,
        token: str,
    ) -> str:
        normalized_token = str(
            token or ""
        ).strip()

        if not normalized_token:
            raise ValueError(
                "Password reset token "
                "is required."
            )

        query = urlencode(
            {
                "token": (
                    normalized_token
                )
            }
        )

        return (
            f"{cls._base_url()}"
            "/reset-password"
            f"?{query}"
        )
