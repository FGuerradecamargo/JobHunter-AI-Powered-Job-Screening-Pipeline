from models.app_user import AppUser
from services.admin_access_audit_service import (
    AdminAccessAuditService,
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
        access_level="admin",
    )


def test_denied_access_preserves_current_operational_user():
    repository = FakeRepository()
    service = AdminAccessAuditService(repository)
    admin = _user("admin-a")
    current_user = _user("user-b")

    service.record_denied(
        authenticated_user=admin,
        active_user=current_user,
        target_user_id="user-c",
    )

    assert repository.calls == [{
        "event_type": "admin.viewing_as.denied",
        "outcome": "denied",
        "authenticated_user_id": "admin-a",
        "active_user_id": "user-b",
        "target_type": "user",
        "target_id": "user-c",
        "metadata": {
            "reauthentication_method": "password",
        },
    }]


def test_started_access_attributes_actor_and_target():
    repository = FakeRepository()
    service = AdminAccessAuditService(repository)

    service.record_started(
        authenticated_user=_user("admin-a"),
        target_user=_user("user-b"),
    )

    event = repository.calls[0]
    assert event["authenticated_user_id"] == "admin-a"
    assert event["active_user_id"] == "user-b"
    assert event["target_id"] == "user-b"
    assert event["outcome"] == "success"


def test_ended_access_returns_operational_user_to_actor():
    repository = FakeRepository()
    service = AdminAccessAuditService(repository)

    service.record_ended(
        authenticated_user=_user("admin-a"),
        previous_active_user=_user("user-b"),
    )

    event = repository.calls[0]
    assert event["event_type"] == "admin.viewing_as.ended"
    assert event["authenticated_user_id"] == "admin-a"
    assert event["active_user_id"] == "admin-a"
    assert event["target_id"] == "user-b"
