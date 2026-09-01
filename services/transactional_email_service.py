from __future__ import annotations

import os

import requests


class TransactionalEmailError(
    RuntimeError
):
    pass


class TransactionalEmailService:
    _RESEND_ENDPOINT = (
        "https://api.resend.com/emails"
    )

    _TIMEOUT_SECONDS = 10

    @staticmethod
    def _required_environment(
        name: str,
    ) -> str:
        value = str(
            os.getenv(name) or ""
        ).strip()

        if not value:
            raise TransactionalEmailError(
                "Transactional email service "
                "is not configured."
            )

        return value

    @classmethod
    def send_email(
        cls,
        *,
        to_email: str,
        subject: str,
        html: str,
        idempotency_key: str | None = None,
    ) -> None:
        normalized_email = str(
            to_email or ""
        ).strip()

        normalized_subject = str(
            subject or ""
        ).strip()

        if not normalized_email:
            raise ValueError(
                "Recipient email is required."
            )

        if not normalized_subject:
            raise ValueError(
                "Email subject is required."
            )

        if not html:
            raise ValueError(
                "Email content is required."
            )

        api_key = (
            cls._required_environment(
                "RESEND_API_KEY"
            )
        )

        from_email = (
            cls._required_environment(
                "EMAIL_FROM"
            )
        )

        headers = {
            "Authorization": (
                f"Bearer {api_key}"
            ),
            "Content-Type": (
                "application/json"
            ),
        }

        if idempotency_key:
            headers[
                "Idempotency-Key"
            ] = str(
                idempotency_key
            )

        payload = {
            "from": from_email,
            "to": [
                normalized_email
            ],
            "subject": (
                normalized_subject
            ),
            "html": html,
        }

        try:
            response = requests.post(
                cls._RESEND_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=(
                    cls._TIMEOUT_SECONDS
                ),
            )

        except requests.RequestException:
            raise TransactionalEmailError(
                "Transactional email service "
                "is temporarily unavailable."
            ) from None

        if not (
            200
            <= response.status_code
            < 300
        ):
            raise TransactionalEmailError(
                "Transactional email service "
                "rejected the request."
            )
