from __future__ import annotations

import hashlib

import requests


class PasswordSecurityUnavailableError(
    ValueError
):
    """Raised when password breach checking is unavailable."""


class CompromisedPasswordService:
    RANGE_URL = (
        "https://api.pwnedpasswords.com/"
        "range/{prefix}"
    )

    TIMEOUT_SECONDS = 5

    @classmethod
    def breach_count(
        cls,
        password: str,
    ) -> int:
        password_hash = hashlib.sha1(
            password.encode("utf-8")
        ).hexdigest().upper()

        prefix = password_hash[:5]
        suffix = password_hash[5:]

        try:
            response = requests.get(
                cls.RANGE_URL.format(
                    prefix=prefix
                ),
                headers={
                    "Add-Padding": "true",
                    "User-Agent": (
                        "WorkPilot/"
                        "password-security"
                    ),
                },
                timeout=(
                    cls.TIMEOUT_SECONDS
                ),
            )

            response.raise_for_status()

        except requests.RequestException as exc:
            raise PasswordSecurityUnavailableError(
                "Password security check "
                "is temporarily unavailable. "
                "Please try again."
            ) from exc

        for line in response.text.splitlines():
            try:
                returned_suffix, count_text = (
                    line.split(":", 1)
                )

                count = int(
                    count_text.strip()
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                returned_suffix.strip().upper()
                == suffix
            ):
                return count

        return 0

    @classmethod
    def is_compromised(
        cls,
        password: str,
    ) -> bool:
        return (
            cls.breach_count(password)
            > 0
        )
