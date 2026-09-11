from models.app_user import AppUser
from services.security_audit_repository import (
    SecurityAuditRepository,
)


class AdminAccessAuditService:
    def __init__(
        self,
        repository: SecurityAuditRepository | None = None,
    ) -> None:
        self.repository = repository or SecurityAuditRepository()

    def record_denied(
        self,
        *,
        authenticated_user: AppUser,
        active_user: AppUser,
        target_user_id: str,
    ) -> str:
        return self.repository.record(
            event_type="admin.viewing_as.denied",
            outcome="denied",
            authenticated_user_id=authenticated_user.id,
            active_user_id=active_user.id,
            target_type="user",
            target_id=target_user_id,
            metadata={
                "reauthentication_method": "password",
            },
        )

    def record_started(
        self,
        *,
        authenticated_user: AppUser,
        target_user: AppUser,
    ) -> str:
        return self.repository.record(
            event_type="admin.viewing_as.started",
            outcome="success",
            authenticated_user_id=authenticated_user.id,
            active_user_id=target_user.id,
            target_type="user",
            target_id=target_user.id,
            metadata={
                "reauthentication_method": "password",
            },
        )

    def record_ended(
        self,
        *,
        authenticated_user: AppUser,
        previous_active_user: AppUser,
    ) -> str:
        return self.repository.record(
            event_type="admin.viewing_as.ended",
            outcome="success",
            authenticated_user_id=authenticated_user.id,
            active_user_id=authenticated_user.id,
            target_type="user",
            target_id=previous_active_user.id,
            metadata={},
        )
