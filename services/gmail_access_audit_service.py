from models.app_user import AppUser
from services.security_audit_repository import (
    SecurityAuditRepository,
)


class GmailAccessAuditService:
    ALLOWED_STAGES = {
        "authorization",
        "callback",
        "provider_callback",
        "state_validation",
        "token_exchange_or_persistence",
        "user_action",
    }

    def __init__(
        self,
        repository: SecurityAuditRepository | None = None,
    ) -> None:
        self.repository = repository or SecurityAuditRepository()

    def record_authorization_started(
        self,
        *,
        authenticated_user: AppUser,
        target_user: AppUser,
    ) -> str:
        return self._record(
            event_type="gmail.authorization.started",
            outcome="success",
            authenticated_user=authenticated_user,
            active_user_id=target_user.id,
            target_user_id=target_user.id,
            stage="authorization",
        )

    def record_authorization_failed(
        self,
        *,
        authenticated_user: AppUser,
        active_user_id: str,
        target_user_id: str = "",
        stage: str,
    ) -> str:
        outcome = (
            "error"
            if stage == "token_exchange_or_persistence"
            else "denied"
        )

        return self._record(
            event_type="gmail.authorization.failed",
            outcome=outcome,
            authenticated_user=authenticated_user,
            active_user_id=active_user_id,
            target_user_id=target_user_id,
            stage=stage,
        )

    def record_connected(
        self,
        *,
        authenticated_user: AppUser,
        target_user_id: str,
    ) -> str:
        return self._record(
            event_type="gmail.connection.completed",
            outcome="success",
            authenticated_user=authenticated_user,
            active_user_id=target_user_id,
            target_user_id=target_user_id,
            stage="callback",
        )

    def record_disconnected(
        self,
        *,
        authenticated_user: AppUser,
        target_user: AppUser,
    ) -> str:
        return self._record(
            event_type="gmail.connection.disconnected",
            outcome="success",
            authenticated_user=authenticated_user,
            active_user_id=target_user.id,
            target_user_id=target_user.id,
            stage="user_action",
        )

    def _record(
        self,
        *,
        event_type: str,
        outcome: str,
        authenticated_user: AppUser,
        active_user_id: str,
        target_user_id: str,
        stage: str,
    ) -> str:
        if stage not in self.ALLOWED_STAGES:
            raise ValueError("Invalid Gmail audit stage.")

        return self.repository.record(
            event_type=event_type,
            outcome=outcome,
            authenticated_user_id=authenticated_user.id,
            active_user_id=active_user_id,
            target_type=(
                "user"
                if target_user_id
                else ""
            ),
            target_id=target_user_id,
            metadata={"stage": stage},
        )
