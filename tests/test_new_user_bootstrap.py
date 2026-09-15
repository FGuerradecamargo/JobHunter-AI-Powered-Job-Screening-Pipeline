from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

import pytest

import services.application_bootstrap as bootstrap_module
import services.database as database_module
from services.auth_service import AuthService


def test_concurrent_sqlite_schema_initialization(monkeypatch, tmp_path):
    database_file = _use_empty_database(monkeypatch, tmp_path)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(
            lambda _: database_module.initialize_sqlite_database(), range(4)
        ))
    assert _rows(database_file, "users") == []
    assert _rows(database_file, "candidates") == []


def test_postgres_bootstrap_locks_before_schema(monkeypatch):
    statements = []

    class StopAfterLock(Exception):
        pass

    class Connection:
        def execute(self, sql):
            statements.append(sql)
            raise StopAfterLock()

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(database_module, "get_connection", connection)
    with pytest.raises(StopAfterLock):
        database_module.initialize_postgres_database()
    assert statements == ["SELECT pg_advisory_xact_lock(731302)"]


def test_signup_commit_failure_rolls_back_and_retry_succeeds(monkeypatch, tmp_path):
    import services.auth_service as auth_module

    database_file = _use_empty_database(monkeypatch, tmp_path)
    bootstrap_module.bootstrap_application()
    service = _service(monkeypatch)
    original_connection = auth_module.get_connection

    @contextmanager
    def rejected_commit():
        with original_connection() as connection:
            yield connection
            raise sqlite3.OperationalError("simulated commit rejection")

    monkeypatch.setattr(auth_module, "get_connection", rejected_commit)
    with pytest.raises(sqlite3.OperationalError):
        service.register("retry@example.com", "Retry", "a sufficiently long password")
    assert _rows(database_file, "users") == []
    assert _rows(database_file, "candidates") == []
    monkeypatch.setattr(auth_module, "get_connection", original_connection)
    service.register("retry@example.com", "Retry", "a sufficiently long password")
    assert len(_rows(database_file, "users")) == 1
    assert len(_rows(database_file, "candidates")) == 1


def _use_empty_database(monkeypatch, tmp_path):
    database_file = tmp_path / "first-run.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database_module, "DATABASE_FILE", database_file)
    database_module.initialize_database.cache_clear()
    monkeypatch.setattr(bootstrap_module, "_bootstrap_complete", False)
    return database_file


def _rows(database_file, table):
    with sqlite3.connect(database_file) as connection:
        return connection.execute(
            f"SELECT * FROM {table}"
        ).fetchall()


def _service(monkeypatch):
    monkeypatch.setattr(
        AuthService,
        "ITERATIONS",
        1,
    )
    monkeypatch.setattr(
        "services.auth_service.CompromisedPasswordService.is_compromised",
        lambda _password: False,
    )
    return AuthService()


def test_empty_sqlite_database_bootstraps_before_first_visit(
    monkeypatch,
    tmp_path,
):
    database_file = _use_empty_database(monkeypatch, tmp_path)

    bootstrap_module.bootstrap_application()

    with sqlite3.connect(database_file) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"users", "candidates", "user_sessions"} <= tables


def test_bootstrap_rerun_preserves_existing_account(
    monkeypatch,
    tmp_path,
):
    database_file = _use_empty_database(monkeypatch, tmp_path)
    bootstrap_module.bootstrap_application()
    service = _service(monkeypatch)
    user = service.register(
        "existing@example.com",
        "Existing User",
        "a sufficiently long password",
    )

    database_module.initialize_database.cache_clear()
    monkeypatch.setattr(bootstrap_module, "_bootstrap_complete", False)
    bootstrap_module.bootstrap_application()

    users = _rows(database_file, "users")
    candidates = _rows(database_file, "candidates")
    assert len(users) == 1
    assert len(candidates) == 1
    assert users[0][0] == user.id
    assert users[0][3] == user.candidate_id


def test_concurrent_bootstrap_initializes_once(monkeypatch):
    calls = 0
    calls_lock = Lock()

    def initialize_once():
        nonlocal calls
        with calls_lock:
            calls += 1
        sleep(0.01)

    monkeypatch.setattr(
        bootstrap_module,
        "initialize_database",
        initialize_once,
    )
    monkeypatch.setattr(bootstrap_module, "_bootstrap_complete", False)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(
            lambda _value: bootstrap_module.bootstrap_application(),
            range(8),
        ))

    assert calls == 1


def test_password_signup_is_atomic_and_complete(
    monkeypatch,
    tmp_path,
):
    database_file = _use_empty_database(monkeypatch, tmp_path)
    bootstrap_module.bootstrap_application()

    user = _service(monkeypatch).register(
        "new@example.com",
        "New User",
        "a sufficiently long password",
    )

    users = _rows(database_file, "users")
    candidates = _rows(database_file, "candidates")
    assert len(users) == 1
    assert len(candidates) == 1
    assert users[0][0] == user.id
    assert users[0][3] == user.candidate_id
    assert users[0][5]


def test_candidate_creation_failure_creates_nothing(
    monkeypatch,
    tmp_path,
):
    database_file = _use_empty_database(monkeypatch, tmp_path)
    bootstrap_module.bootstrap_application()
    service = _service(monkeypatch)

    def fail_candidate(_connection, _candidate):
        raise RuntimeError("candidate insert failed")

    monkeypatch.setattr(
        service.candidate_repository,
        "create_with_connection",
        fail_candidate,
    )

    with pytest.raises(RuntimeError):
        service.register(
            "new@example.com",
            "New User",
            "a sufficiently long password",
        )

    assert _rows(database_file, "users") == []
    assert _rows(database_file, "candidates") == []


def test_user_creation_failure_rolls_back_candidate(
    monkeypatch,
    tmp_path,
):
    database_file = _use_empty_database(monkeypatch, tmp_path)
    bootstrap_module.bootstrap_application()
    service = _service(monkeypatch)

    def fail_user(*_args, **_kwargs):
        raise RuntimeError("user insert failed")

    monkeypatch.setattr(
        service.user_repository,
        "create_with_connection",
        fail_user,
    )

    with pytest.raises(RuntimeError):
        service.register(
            "new@example.com",
            "New User",
            "a sufficiently long password",
        )

    assert _rows(database_file, "users") == []
    assert _rows(database_file, "candidates") == []


def test_repeated_signup_does_not_duplicate_candidate(
    monkeypatch,
    tmp_path,
):
    database_file = _use_empty_database(monkeypatch, tmp_path)
    bootstrap_module.bootstrap_application()
    service = _service(monkeypatch)
    values = (
        "same@example.com",
        "Same User",
        "a sufficiently long password",
    )

    first_user = service.register(*values)
    with pytest.raises(ValueError):
        service.register(*values)

    assert len(_rows(database_file, "users")) == 1
    assert len(_rows(database_file, "candidates")) == 1
    assert _rows(database_file, "users")[0][3] == first_user.candidate_id


def test_repeated_login_does_not_create_candidate(
    monkeypatch,
    tmp_path,
):
    database_file = _use_empty_database(monkeypatch, tmp_path)
    bootstrap_module.bootstrap_application()
    service = _service(monkeypatch)
    password = "a sufficiently long password"
    registered = service.register(
        "login@example.com",
        "Login User",
        password,
    )

    first = service.authenticate("login@example.com", password)
    second = service.authenticate("login@example.com", password)

    assert first.candidate_id == registered.candidate_id
    assert second.candidate_id == registered.candidate_id
    assert len(_rows(database_file, "candidates")) == 1


def test_bootstrap_source_has_no_external_clients():
    source = (
        __import__("pathlib")
        .Path("services/application_bootstrap.py")
        .read_text(encoding="utf-8")
        .casefold()
    )

    assert "openai" not in source
    assert "gmail" not in source
    assert "requests" not in source
    assert "google" not in source
