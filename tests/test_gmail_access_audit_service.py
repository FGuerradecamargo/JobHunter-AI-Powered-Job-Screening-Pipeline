from models.app_user import AppUser
import pytest

from services.gmail_access_audit_service import (
    GmailAccessAuditService,
)


class FakeRepository:
    def __init__(self):
        self.calls = []

    def record(self, **values):
        self.calls.append(values)
        return "event-id"


def _user(user_id: str) -> AppUser:
    return AppUser(
        id=user_id,
        email=f"{user_id}@example.com",
        display_name=user_id,
    )


def test_authorization_started_attributes_admin_and_target():
    repository = FakeRepository()
    service = GmailAccessAuditService(repository)

    service.record_authorization_started(
        authenticated_user=_user("admin-a"),
        target_user=_user("user-b"),
    )

    event = repository.calls[0]
    assert event["event_type"] == "gmail.authorization.started"
    assert event["authenticated_user_id"] == "admin-a"
    assert event["active_user_id"] == "user-b"
    assert event["target_id"] == "user-b"
    assert event["metadata"] == {"stage": "authorization"}


def test_untrusted_callback_failure_has_no_target():
    repository = FakeRepository()
    service = GmailAccessAuditService(repository)

    service.record_authorization_failed(
        authenticated_user=_user("admin-a"),
        active_user_id="user-b",
        stage="state_validation",
    )

    event = repository.calls[0]
    assert event["outcome"] == "denied"
    assert event["active_user_id"] == "user-b"
    assert event["target_type"] == ""
    assert event["target_id"] == ""
    assert event["metadata"] == {"stage": "state_validation"}


def test_trusted_callback_failure_uses_state_target():
    repository = FakeRepository()
    service = GmailAccessAuditService(repository)

    service.record_authorization_failed(
        authenticated_user=_user("admin-a"),
        active_user_id="user-b",
        target_user_id="user-b",
        stage="token_exchange_or_persistence",
    )

    event = repository.calls[0]
    assert event["outcome"] == "error"
    assert event["target_type"] == "user"
    assert event["target_id"] == "user-b"


def test_connection_completed_contains_no_gmail_or_oauth_data():
    repository = FakeRepository()
    service = GmailAccessAuditService(repository)

    service.record_connected(
        authenticated_user=_user("admin-a"),
        target_user_id="user-b",
    )

    event = repository.calls[0]
    assert event["event_type"] == "gmail.connection.completed"
    assert event["authenticated_user_id"] == "admin-a"
    assert event["active_user_id"] == "user-b"
    assert event["target_id"] == "user-b"
    assert event["metadata"] == {"stage": "callback"}


def test_disconnect_attributes_actor_and_operational_user():
    repository = FakeRepository()
    service = GmailAccessAuditService(repository)

    service.record_disconnected(
        authenticated_user=_user("admin-a"),
        target_user=_user("user-b"),
    )

    event = repository.calls[0]
    assert event["event_type"] == (
        "gmail.connection.disconnected"
    )
    assert event["authenticated_user_id"] == "admin-a"
    assert event["active_user_id"] == "user-b"
    assert event["target_id"] == "user-b"


def test_rejects_uncontrolled_stage_metadata():
    repository = FakeRepository()
    service = GmailAccessAuditService(repository)

    with pytest.raises(
        ValueError,
        match="Invalid Gmail audit stage",
    ):
        service.record_authorization_failed(
            authenticated_user=_user("admin-a"),
            active_user_id="user-b",
            stage="provider said something sensitive",
        )

    assert repository.calls == []
