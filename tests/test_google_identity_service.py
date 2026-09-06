from __future__ import annotations

import pytest

from models.app_user import AppUser
from services.google_identity_service import (
    GoogleIdentityService,
)


class FakeIdentityRepository:
    def __init__(
        self,
        linked_user_id=None,
    ):
        self.linked_user_id = linked_user_id
        self.recorded = []

    def record_authentication(
        self,
        *,
        provider,
        subject,
        provider_email=None,
    ):
        self.recorded.append(
            (
                provider,
                subject,
                provider_email,
            )
        )

        return self.linked_user_id


class FakeUserRepository:
    def __init__(
        self,
        *,
        user_by_id=None,
        user_by_email=None,
    ):
        self.user_by_id = user_by_id
        self.user_by_email = user_by_email

    def get_by_id(
        self,
        user_id,
    ):
        if (
            self.user_by_id is not None
            and self.user_by_id.id == user_id
        ):
            return self.user_by_id

        return None

    def get_by_email(
        self,
        email,
    ):
        if (
            self.user_by_email is not None
            and self.user_by_email.email == email
        ):
            return self.user_by_email

        return None


def _user():
    return AppUser(
        id="workpilot-user",
        email="user@example.com",
        display_name="WorkPilot User",
        candidate_id=None,
        access_level="user",
    )


def _claims(
    **overrides,
):
    claims = {
        "sub": "google-subject-1",
        "email": "USER@EXAMPLE.COM",
        "email_verified": True,
        "name": "Google User",
    }

    claims.update(
        overrides
    )

    return claims


def _service(
    *,
    linked_user_id=None,
    user_by_id=None,
    user_by_email=None,
):
    service = GoogleIdentityService()

    service.identity_repository = (
        FakeIdentityRepository(
            linked_user_id=linked_user_id,
        )
    )

    service.user_repository = (
        FakeUserRepository(
            user_by_id=user_by_id,
            user_by_email=user_by_email,
        )
    )

    return service


def test_linked_google_identity_resolves_existing_user():
    user = _user()

    service = _service(
        linked_user_id=user.id,
        user_by_id=user,
    )

    result = service.resolve(
        _claims()
    )

    assert (
        result.status
        == GoogleIdentityService.LINKED
    )

    assert result.user == user
    assert (
        result.subject
        == "google-subject-1"
    )
    assert (
        result.email
        == "user@example.com"
    )
    assert (
        result.display_name
        == "Google User"
    )

    assert (
        service.identity_repository
        .recorded
        == [
            (
                "google",
                "google-subject-1",
                "user@example.com",
            )
        ]
    )


def test_existing_email_requires_explicit_link():
    user = _user()

    service = _service(
        user_by_email=user,
    )

    result = service.resolve(
        _claims()
    )

    assert (
        result.status
        == GoogleIdentityService.LINK_REQUIRED
    )

    assert result.user == user


def test_new_google_identity_requires_registration():
    service = _service()

    result = service.resolve(
        _claims(
            email="new@example.com",
        )
    )

    assert (
        result.status
        == GoogleIdentityService
        .REGISTRATION_REQUIRED
    )

    assert result.user is None
    assert (
        result.email
        == "new@example.com"
    )


def test_missing_google_subject_is_rejected():
    service = _service()

    with pytest.raises(
        ValueError,
        match="Google identity subject is missing",
    ):
        service.resolve(
            _claims(
                sub="",
            )
        )


def test_missing_google_email_is_rejected():
    service = _service()

    with pytest.raises(
        ValueError,
        match="Google identity email is missing",
    ):
        service.resolve(
            _claims(
                email="",
            )
        )


@pytest.mark.parametrize(
    "verified_value",
    [
        False,
        None,
        "true",
        1,
    ],
)
def test_unverified_google_email_is_rejected(
    verified_value,
):
    service = _service()

    with pytest.raises(
        ValueError,
        match="Google email is not verified",
    ):
        service.resolve(
            _claims(
                email_verified=verified_value,
            )
        )


def test_missing_google_name_falls_back_to_email():
    service = _service()

    result = service.resolve(
        _claims(
            name="",
        )
    )

    assert (
        result.display_name
        == "user@example.com"
    )


def test_broken_linked_identity_is_rejected():
    service = _service(
        linked_user_id="missing-user",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Linked Google identity "
            "references a missing user"
        ),
    ):
        service.resolve(
            _claims()
        )
