from contextlib import contextmanager
import json

import pytest

import services.database as database_module
import services.security_audit_repository as repository_module
from services.security_audit_repository import (
    SecurityAuditRepository,
)


class FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))
        return self


def _repository(monkeypatch):
    connection = FakeConnection()

    @contextmanager
    def fake_get_connection():
        yield connection

    monkeypatch.setattr(
        repository_module,
        "get_connection",
        fake_get_connection,
    )

    return SecurityAuditRepository(), connection


def test_records_actor_active_user_and_safe_metadata(monkeypatch):
    repository, connection = _repository(monkeypatch)

    event_id = repository.record(
        event_type="admin.viewing_as.started",
        outcome="success",
        authenticated_user_id="admin-a",
        active_user_id="user-b",
        target_type="user",
        target_id="user-b",
        metadata={"reauthentication_method": "password"},
    )

    insert_sql, params = next(
        call
        for call in connection.calls
        if call[0].startswith(
            "INSERT INTO security_audit_events"
        )
    )

    assert len(event_id) == 32
    assert "authenticated_user_id" in insert_sql
    assert "active_user_id" in insert_sql
    assert params[1:8] == (
        "admin.viewing_as.started",
        "success",
        "admin-a",
        "user-b",
        "user",
        "user-b",
        json.dumps(
            {"reauthentication_method": "password"},
            ensure_ascii=True,
            sort_keys=True,
        ),
    )


def test_records_with_existing_connection(monkeypatch):
    repository, connection = _repository(monkeypatch)

    event_id = repository.record_with_connection(
        connection,
        event_type="account.password_reset.completed",
        outcome="success",
        authenticated_user_id="user-a",
        active_user_id="user-a",
        target_type="user",
        target_id="user-a",
    )

    assert len(event_id) == 32
    assert any(
        sql.startswith("INSERT INTO security_audit_events")
        for sql, _ in connection.calls
    )


def test_records_event_in_sqlite(
    monkeypatch,
    tmp_path,
):
    database_file = tmp_path / "audit.db"

    monkeypatch.delenv(
        "DATABASE_URL",
        raising=False,
    )
    monkeypatch.setattr(
        database_module,
        "DATABASE_FILE",
        database_file,
    )

    repository = SecurityAuditRepository()
    event_id = repository.record(
        event_type="admin.viewing_as.started",
        outcome="success",
        authenticated_user_id="admin-a",
        active_user_id="user-b",
        target_type="user",
        target_id="user-b",
        metadata={"method": "password"},
    )

    with database_module.get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM security_audit_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()

    assert row is not None
    assert row["authenticated_user_id"] == "admin-a"
    assert row["active_user_id"] == "user-b"
    assert json.loads(row["metadata_json"]) == {
        "method": "password"
    }


@pytest.mark.parametrize(
    "metadata",
    [
        {"password": "value"},
        {"refresh_token": "value"},
        {"client_secret": "value"},
        {"cookie_value": "value"},
        {"authorization_header": "value"},
    ],
)
def test_rejects_sensitive_metadata(monkeypatch, metadata):
    repository, connection = _repository(monkeypatch)

    with pytest.raises(
        ValueError,
        match="Sensitive audit metadata",
    ):
        repository.record(
            event_type="security.test",
            outcome="denied",
            authenticated_user_id="admin-a",
            active_user_id="admin-a",
            metadata=metadata,
        )

    assert connection.calls == []


def test_rejects_nested_metadata(monkeypatch):
    repository, connection = _repository(monkeypatch)

    with pytest.raises(
        ValueError,
        match="must be scalar",
    ):
        repository.record(
            event_type="security.test",
            outcome="error",
            authenticated_user_id="admin-a",
            active_user_id="admin-a",
            metadata={"details": {"unsafe": "shape"}},
        )

    assert connection.calls == []


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("event_type", "", "Event type is required"),
        ("outcome", "unknown", "Invalid audit outcome"),
        (
            "authenticated_user_id",
            "",
            "Authenticated user ID is required",
        ),
        (
            "active_user_id",
            "",
            "Active user ID is required",
        ),
    ],
)
def test_rejects_invalid_required_fields(
    monkeypatch,
    field,
    value,
    message,
):
    repository, connection = _repository(monkeypatch)
    values = {
        "event_type": "security.test",
        "outcome": "success",
        "authenticated_user_id": "admin-a",
        "active_user_id": "admin-a",
    }
    values[field] = value

    with pytest.raises(ValueError, match=message):
        repository.record(**values)

    assert connection.calls == []
