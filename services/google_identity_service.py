from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from models.app_user import AppUser
from services.user_identity_repository import (
    UserIdentityRepository,
)
from services.user_repository import UserRepository


@dataclass(frozen=True)
class GoogleIdentityResolution:
    status: str
    subject: str
    email: str
    display_name: str
    user: AppUser | None = None


class GoogleIdentityService:
    PROVIDER = "google"

    LINKED = "linked"
    LINK_REQUIRED = "link_required"
    REGISTRATION_REQUIRED = (
        "registration_required"
    )

    def __init__(self) -> None:
        self.identity_repository = (
            UserIdentityRepository()
        )
        self.user_repository = (
            UserRepository()
        )

    @staticmethod
    def _read_text_claim(
        claims: Mapping[str, object],
        key: str,
    ) -> str:
        return str(
            claims.get(
                key,
                "",
            )
            or ""
        ).strip()

    @classmethod
    def _validate_claims(
        cls,
        claims: Mapping[str, object],
    ) -> tuple[str, str, str]:
        subject = cls._read_text_claim(
            claims,
            "sub",
        )

        if not subject:
            raise ValueError(
                "Google identity subject is missing."
            )

        email = cls._read_text_claim(
            claims,
            "email",
        ).lower()

        if not email:
            raise ValueError(
                "Google identity email is missing."
            )

        if claims.get(
            "email_verified"
        ) is not True:
            raise ValueError(
                "Google email is not verified."
            )

        display_name = cls._read_text_claim(
            claims,
            "name",
        )

        if not display_name:
            display_name = email

        return (
            subject,
            email,
            display_name,
        )

    def resolve(
        self,
        claims: Mapping[str, object],
    ) -> GoogleIdentityResolution:
        (
            subject,
            email,
            display_name,
        ) = self._validate_claims(
            claims
        )

        linked_user_id = (
            self.identity_repository
            .record_authentication(
                provider=self.PROVIDER,
                subject=subject,
                provider_email=email,
            )
        )

        if linked_user_id is not None:
            user = (
                self.user_repository
                .get_by_id(
                    linked_user_id
                )
            )

            if user is None:
                raise RuntimeError(
                    "Linked Google identity "
                    "references a missing user."
                )

            return GoogleIdentityResolution(
                status=self.LINKED,
                subject=subject,
                email=email,
                display_name=display_name,
                user=user,
            )

        existing_user = (
            self.user_repository
            .get_by_email(
                email
            )
        )

        if existing_user is not None:
            return GoogleIdentityResolution(
                status=self.LINK_REQUIRED,
                subject=subject,
                email=email,
                display_name=display_name,
                user=existing_user,
            )

        return GoogleIdentityResolution(
            status=(
                self.REGISTRATION_REQUIRED
            ),
            subject=subject,
            email=email,
            display_name=display_name,
        )
