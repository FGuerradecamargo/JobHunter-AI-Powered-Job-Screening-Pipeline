from __future__ import annotations

from models.app_user import AppUser
from models.user_context import UserContext
from services.access_policy import AccessPolicy
from services.user_repository import UserRepository


class UserContextService:
    def __init__(self) -> None:
        self.user_repository = (
            UserRepository()
        )

    def resolve(
        self,
        *,
        authenticated_user: AppUser,
        active_user_id: str | None = None,
    ) -> UserContext:
        normalized_active_user_id = str(
            active_user_id or ""
        ).strip()

        # Default operational context is always
        # the authenticated account itself.
        if (
            not normalized_active_user_id
            or normalized_active_user_id
            == authenticated_user.id
        ):
            return UserContext(
                authenticated_user=(
                    authenticated_user
                ),
                active_user=authenticated_user,
            )

        # A normal user must never be able to
        # switch operational context.
        if not AccessPolicy.can_view_all_users(
            authenticated_user
        ):
            raise PermissionError(
                "User cannot change active account."
            )

        active_user = (
            self.user_repository.get_by_id(
                normalized_active_user_id
            )
        )

        if active_user is None:
            raise ValueError(
                "Active user was not found."
            )

        return UserContext(
            authenticated_user=(
                authenticated_user
            ),
            active_user=active_user,
        )
