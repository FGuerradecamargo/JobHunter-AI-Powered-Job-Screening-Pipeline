from models.app_user import AppUser
from services.access_policy import AccessPolicy
from services.auth_service import AuthService


class AdminReauthenticationService:
    def __init__(
        self,
        auth_service: AuthService | None = None,
    ) -> None:
        self.auth_service = auth_service or AuthService()

    def reauthenticate(
        self,
        *,
        authenticated_user: AppUser,
        password: str,
    ) -> bool:
        if not AccessPolicy.can_view_all_users(
            authenticated_user
        ):
            return False

        verified_user = self.auth_service.authenticate(
            email=authenticated_user.email,
            password=password,
        )

        return bool(
            verified_user
            and verified_user.id == authenticated_user.id
            and AccessPolicy.can_view_all_users(
                verified_user
            )
        )
