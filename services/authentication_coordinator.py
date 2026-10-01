from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from models.app_user import AppUser
from services.auth_service import AuthService
from services.google_account_service import GoogleAccountService
from services.google_identity_service import GoogleIdentityResolution, GoogleIdentityService


@dataclass(frozen=True)
class GoogleAuthenticationResult:
    status: str
    resolution: GoogleIdentityResolution
    user: AppUser | None


class AuthenticationCoordinator:
    def __init__(
        self,
        *,
        auth_service: AuthService | None = None,
        google_identity_service: GoogleIdentityService | None = None,
        google_account_service: GoogleAccountService | None = None,
        session_login: Callable[[AppUser], None] | None = None,
    ) -> None:
        self.auth_service = auth_service if auth_service is not None else AuthService()
        self.google_identity_service = (
            google_identity_service
            if google_identity_service is not None else GoogleIdentityService()
        )
        self.google_account_service = (
            google_account_service
            if google_account_service is not None else GoogleAccountService()
        )
        self.session_login = session_login

    def _login(self, user: AppUser) -> None:
        if self.session_login is not None:
            self.session_login(user)
        else:
            from services.session_auth import login_user

            login_user(user)

    def authenticate_with_password(self, email: str, password: str) -> AppUser | None:
        user = self.auth_service.authenticate(email, password)
        if user is not None:
            self._login(user)
        return user

    def authenticate_with_google(
        self, claims: Mapping[str, object],
    ) -> GoogleAuthenticationResult:
        resolution = self.google_identity_service.resolve(claims)
        if resolution.status == GoogleIdentityService.LINKED:
            user = resolution.user
            if user is None:
                raise RuntimeError("Linked Google identity has no user.")
        elif resolution.status == GoogleIdentityService.REGISTRATION_REQUIRED:
            user = self.google_account_service.register(resolution)
        elif resolution.status == GoogleIdentityService.LINK_REQUIRED:
            return GoogleAuthenticationResult(resolution.status, resolution, None)
        else:
            raise RuntimeError("Unknown Google identity status.")
        self._login(user)
        return GoogleAuthenticationResult(resolution.status, resolution, user)

    def link_google_with_password(
        self, resolution: GoogleIdentityResolution, password: str,
    ) -> AppUser | None:
        if resolution.status != GoogleIdentityService.LINK_REQUIRED:
            raise ValueError("Google identity is not eligible for account linking.")
        authenticated_user = self.auth_service.authenticate(resolution.email, password)
        if authenticated_user is None:
            return None
        linked_user = self.google_account_service.link_existing_account(
            resolution=resolution, authenticated_user=authenticated_user,
        )
        self._login(linked_user)
        return linked_user
