from __future__ import annotations

from models.app_user import AppUser
from models.user_context import UserContext
from services.active_user_session import ActiveUserSession
from services.user_context_service import UserContextService


class ActiveUserContextService:
    def __init__(
        self,
        *,
        active_user_session: ActiveUserSession,
        user_context_service: UserContextService | None = None,
    ) -> None:
        self.active_user_session = (
            active_user_session
        )
        self.user_context_service = (
            user_context_service
            or UserContextService()
        )

    def resolve(
        self,
        *,
        authenticated_user: AppUser,
    ) -> UserContext:
        active_user_id = (
            self.active_user_session
            .get_active_user_id(
                authenticated_user_id=(
                    authenticated_user.id
                )
            )
        )

        try:
            return (
                self.user_context_service.resolve(
                    authenticated_user=(
                        authenticated_user
                    ),
                    active_user_id=(
                        active_user_id
                    ),
                )
            )

        except (
            PermissionError,
            ValueError,
        ):
            self.active_user_session.reset(
                authenticated_user_id=(
                    authenticated_user.id
                )
            )

            return (
                self.user_context_service.resolve(
                    authenticated_user=(
                        authenticated_user
                    )
                )
            )

    def activate(
        self,
        *,
        authenticated_user: AppUser,
        active_user_id: str,
    ) -> UserContext:
        # Returning to the authenticated account is
        # not impersonation. Clear the operational
        # override and resolve the default context.
        if (
            str(active_user_id).strip()
            == authenticated_user.id
        ):
            self.active_user_session.reset(
                authenticated_user_id=(
                    authenticated_user.id
                )
            )

            return (
                self.user_context_service.resolve(
                    authenticated_user=(
                        authenticated_user
                    )
                )
            )

        # Any different target must be authorized and
        # resolved before it is persisted in session.
        context = (
            self.user_context_service.resolve(
                authenticated_user=(
                    authenticated_user
                ),
                active_user_id=active_user_id,
            )
        )

        self.active_user_session.set_active_user_id(
            authenticated_user_id=(
                authenticated_user.id
            ),
            active_user_id=(
                context.active_user.id
            ),
        )

        return context
