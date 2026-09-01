from __future__ import annotations

import hashlib
import os

import pytest

from services.auth_rate_limiter import AuthRateLimiter
from services.auth_service import AuthService
from services.compromised_password_service import (
    CompromisedPasswordService,
    PasswordSecurityUnavailableError,
)




@pytest.fixture(autouse=True)
def _disable_external_breach_lookup(
    monkeypatch,
):
    monkeypatch.setattr(
        CompromisedPasswordService,
        "is_compromised",
        classmethod(
            lambda cls, password: False
        ),
    )


def _build_legacy_hash(
    password: str,
    *,
    iterations: int = 310_000,
) -> str:
    salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )

    return (
        f"{iterations}$"
        f"{salt.hex()}$"
        f"{password_hash.hex()}"
    )


def test_new_password_hash_uses_current_cost():
    password = "correct horse battery staple"

    stored_hash = AuthService.hash_password(
        password
    )

    iterations_text, _, _ = (
        stored_hash.split("$")
    )

    assert int(iterations_text) == 600_000

    assert AuthService.verify_password(
        password,
        stored_hash,
    )


def test_password_shorter_than_minimum_is_rejected():
    with pytest.raises(
        ValueError,
        match="at least 15 characters",
    ):
        AuthService.hash_password(
            "too-short"
        )


def test_password_longer_than_maximum_is_rejected():
    with pytest.raises(
        ValueError,
        match="at most 128 characters",
    ):
        AuthService.hash_password(
            "x" * 129
        )


def test_password_boundary_lengths_are_allowed():
    minimum_password = "x" * 15
    maximum_password = "y" * 128

    minimum_hash = (
        AuthService.hash_password(
            minimum_password
        )
    )

    maximum_hash = (
        AuthService.hash_password(
            maximum_password
        )
    )

    assert AuthService.verify_password(
        minimum_password,
        minimum_hash,
    )

    assert AuthService.verify_password(
        maximum_password,
        maximum_hash,
    )


def test_spaces_and_unicode_are_allowed():
    password = (
        "Minha senha longa 🔐 segura"
    )

    stored_hash = AuthService.hash_password(
        password
    )

    assert AuthService.verify_password(
        password,
        stored_hash,
    )


def test_legacy_310k_hash_still_verifies():
    password = (
        "legacy password example"
    )

    legacy_hash = _build_legacy_hash(
        password,
        iterations=310_000,
    )

    assert legacy_hash.startswith(
        "310000$"
    )

    assert AuthService.verify_password(
        password,
        legacy_hash,
    )


def test_wrong_password_does_not_verify():
    stored_hash = (
        AuthService.hash_password(
            "this password is correct"
        )
    )

    assert not AuthService.verify_password(
        "this password is wrong",
        stored_hash,
    )


def test_malformed_hash_is_rejected_safely():
    assert not AuthService.verify_password(
        "some password value",
        "not-a-valid-password-hash",
    )


from contextlib import contextmanager
from types import SimpleNamespace

import services.auth_service as auth_module


class _AuthCursor:
    def __init__(
        self,
        *,
        row=None,
        rowcount=0,
    ):
        self._row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self._row


class _AuthConnection:
    def __init__(
        self,
        *,
        user_id,
        email,
        password_hash,
    ):
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash
        self.update_count = 0

    def execute(
        self,
        sql,
        params=(),
    ):
        normalized = " ".join(
            sql.split()
        )

        if normalized.startswith(
            "SELECT id, password_hash FROM users"
        ):
            requested_email = params[0]

            if requested_email != self.email:
                return _AuthCursor(
                    row=None
                )

            return _AuthCursor(
                row={
                    "id": self.user_id,
                    "password_hash": (
                        self.password_hash
                    ),
                }
            )

        if normalized.startswith(
            "UPDATE users SET password_hash"
        ):
            if len(params) == 3:
                (
                    new_hash,
                    _updated_at,
                    user_id,
                ) = params

                if user_id == self.user_id:
                    self.password_hash = new_hash
                    self.update_count += 1

                    return _AuthCursor(
                        rowcount=1
                    )

                return _AuthCursor(
                    rowcount=0
                )

            (
                new_hash,
                _updated_at,
                user_id,
                expected_old_hash,
            ) = params

            if (
                user_id == self.user_id
                and expected_old_hash
                == self.password_hash
            ):
                self.password_hash = new_hash
                self.update_count += 1

                return _AuthCursor(
                    rowcount=1
                )

            return _AuthCursor(
                rowcount=0
            )

        raise AssertionError(
            f"Unexpected SQL: {normalized}"
        )


def _build_auth_service_for_test(
    user,
):
    service = AuthService.__new__(
        AuthService
    )

    class FakeUserRepository:
        def get_by_id(
            self,
            user_id,
        ):
            if user_id == user.id:
                return user

            return None

    service.user_repository = (
        FakeUserRepository()
    )

    return service


def _patch_auth_connection(
    monkeypatch,
    connection,
):
    @contextmanager
    def fake_get_connection():
        yield connection

    @contextmanager
    def fake_serialized_attempt(
        cls,
        identifier,
    ):
        yield connection

    def never_limited(
        cls,
        locked_connection,
        identifier,
        now=None,
    ):
        return False

    def ignore_failure(
        cls,
        locked_connection,
        identifier,
        now=None,
    ):
        return None

    def ignore_clear(
        cls,
        locked_connection,
        identifier,
    ):
        return None

    monkeypatch.setattr(
        auth_module,
        "get_connection",
        fake_get_connection,
    )

    monkeypatch.setattr(
        AuthRateLimiter,
        "serialized_attempt",
        classmethod(
            fake_serialized_attempt
        ),
    )

    monkeypatch.setattr(
        AuthRateLimiter,
        "is_limited_with_connection",
        classmethod(
            never_limited
        ),
    )

    monkeypatch.setattr(
        AuthRateLimiter,
        "record_failure_with_connection",
        classmethod(
            ignore_failure
        ),
    )

    monkeypatch.setattr(
        AuthRateLimiter,
        "clear_with_connection",
        classmethod(
            ignore_clear
        ),
    )


def test_legacy_short_password_upgrades_on_login(
    monkeypatch,
):
    password = "old-pass-1"

    assert (
        len(password)
        < AuthService.MIN_PASSWORD_LENGTH
    )

    legacy_hash = _build_legacy_hash(
        password,
        iterations=310_000,
    )

    user = SimpleNamespace(
        id="user_legacy_1",
        email="legacy@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=legacy_hash,
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    authenticated = service.authenticate(
        " LEGACY@example.com ",
        password,
    )

    assert authenticated is user
    assert connection.update_count == 1

    assert connection.password_hash.startswith(
        "600000$"
    )

    assert AuthService.verify_password(
        password,
        connection.password_hash,
    )


def test_current_password_hash_is_not_rehashed(
    monkeypatch,
):
    password = (
        "already current password"
    )

    current_hash = (
        AuthService.hash_password(
            password
        )
    )

    user = SimpleNamespace(
        id="user_current_1",
        email="current@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=current_hash,
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    authenticated = service.authenticate(
        user.email,
        password,
    )

    assert authenticated is user
    assert connection.update_count == 0
    assert (
        connection.password_hash
        == current_hash
    )


def test_wrong_legacy_password_does_not_rehash(
    monkeypatch,
):
    legacy_hash = _build_legacy_hash(
        "old-pass-1",
        iterations=310_000,
    )

    user = SimpleNamespace(
        id="user_legacy_2",
        email="legacy2@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=legacy_hash,
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    authenticated = service.authenticate(
        user.email,
        "wrong-password",
    )

    assert authenticated is None
    assert connection.update_count == 0
    assert (
        connection.password_hash
        == legacy_hash
    )



def test_compromised_password_is_rejected(
    monkeypatch,
):
    monkeypatch.setattr(
        CompromisedPasswordService,
        "is_compromised",
        classmethod(
            lambda cls, password: True
        ),
    )

    with pytest.raises(
        ValueError,
        match="known data breach",
    ):
        AuthService.hash_password(
            "correct horse battery staple"
        )


def test_breach_service_unavailable_blocks_new_password(
    monkeypatch,
):
    def unavailable(
        cls,
        password,
    ):
        raise PasswordSecurityUnavailableError(
            "Password security check "
            "is temporarily unavailable. "
            "Please try again."
        )

    monkeypatch.setattr(
        CompromisedPasswordService,
        "is_compromised",
        classmethod(unavailable),
    )

    with pytest.raises(
        ValueError,
        match="temporarily unavailable",
    ):
        AuthService.hash_password(
            "another sufficiently long password"
        )


def test_login_and_legacy_rehash_do_not_call_hibp(
    monkeypatch,
):
    password = "old-pass-1"

    legacy_hash = _build_legacy_hash(
        password,
        iterations=310_000,
    )

    user = SimpleNamespace(
        id="user_no_hibp_login",
        email="nohibp@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=legacy_hash,
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    def must_not_be_called(
        cls,
        supplied_password,
    ):
        raise AssertionError(
            "HIBP must not be called during login."
        )

    monkeypatch.setattr(
        CompromisedPasswordService,
        "is_compromised",
        classmethod(
            must_not_be_called
        ),
    )

    authenticated = service.authenticate(
        user.email,
        password,
    )

    assert authenticated is user
    assert connection.update_count == 1

    assert connection.password_hash.startswith(
        "600000$"
    )


def test_unknown_email_uses_dummy_password_hash(
    monkeypatch,
):
    user = SimpleNamespace(
        id="unused_user",
        email="existing@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=(
            AuthService._build_password_hash(
                "existing password",
                iterations=(
                    AuthService.ITERATIONS
                ),
            )
        ),
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    calls = []

    def fake_verify(
        cls,
        password,
        stored_hash,
    ):
        calls.append(
            (
                password,
                stored_hash,
            )
        )
        return False

    monkeypatch.setattr(
        AuthService,
        "verify_password",
        classmethod(fake_verify),
    )

    authenticated = service.authenticate(
        "missing@example.com",
        "attempted password",
    )

    assert authenticated is None

    assert calls == [
        (
            "attempted password",
            AuthService.DUMMY_PASSWORD_HASH,
        )
    ]


def test_account_without_local_password_uses_dummy_hash(
    monkeypatch,
):
    user = SimpleNamespace(
        id="user_google_only",
        email="googleonly@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=None,
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    calls = []

    def fake_verify(
        cls,
        password,
        stored_hash,
    ):
        calls.append(
            stored_hash
        )
        return False

    monkeypatch.setattr(
        AuthService,
        "verify_password",
        classmethod(fake_verify),
    )

    authenticated = service.authenticate(
        user.email,
        "attempted password",
    )

    assert authenticated is None

    assert calls == [
        AuthService.DUMMY_PASSWORD_HASH
    ]


def test_existing_wrong_password_does_not_use_dummy_hash(
    monkeypatch,
):
    stored_hash = (
        AuthService._build_password_hash(
            "correct password",
            iterations=(
                AuthService.ITERATIONS
            ),
        )
    )

    user = SimpleNamespace(
        id="user_existing_wrong",
        email="existingwrong@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=stored_hash,
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    calls = []

    def fake_verify(
        cls,
        password,
        supplied_hash,
    ):
        calls.append(
            supplied_hash
        )
        return False

    monkeypatch.setattr(
        AuthService,
        "verify_password",
        classmethod(fake_verify),
    )

    authenticated = service.authenticate(
        user.email,
        "wrong password",
    )

    assert authenticated is None

    assert calls == [
        stored_hash
    ]

    assert (
        AuthService.DUMMY_PASSWORD_HASH
        not in calls
    )



def test_rate_limited_login_stops_before_password_check(
    monkeypatch,
):
    user = SimpleNamespace(
        id="user_limited",
        email="limited@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=(
            AuthService._build_password_hash(
                "correct password",
                iterations=(
                    AuthService.ITERATIONS
                ),
            )
        ),
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    def limited(
        cls,
        locked_connection,
        identifier,
        now=None,
    ):
        assert (
            locked_connection
            is connection
        )
        return True

    monkeypatch.setattr(
        AuthRateLimiter,
        "is_limited_with_connection",
        classmethod(limited),
    )

    def must_not_verify(
        cls,
        password,
        stored_hash,
    ):
        raise AssertionError(
            "PBKDF2 must not run while "
            "the identifier is rate limited."
        )

    monkeypatch.setattr(
        AuthService,
        "verify_password",
        classmethod(
            must_not_verify
        ),
    )

    authenticated = service.authenticate(
        user.email,
        "attempted password",
    )

    assert authenticated is None


def test_failed_login_records_failure_on_locked_connection(
    monkeypatch,
):
    password = "correct password"

    user = SimpleNamespace(
        id="user_failed_rate",
        email="failed@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=(
            AuthService._build_password_hash(
                password,
                iterations=(
                    AuthService.ITERATIONS
                ),
            )
        ),
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    recorded = []

    def record_failure(
        cls,
        locked_connection,
        identifier,
        now=None,
    ):
        recorded.append(
            (
                locked_connection,
                identifier,
            )
        )

    monkeypatch.setattr(
        AuthRateLimiter,
        "record_failure_with_connection",
        classmethod(
            record_failure
        ),
    )

    authenticated = service.authenticate(
        user.email,
        "wrong password",
    )

    assert authenticated is None

    assert recorded == [
        (
            connection,
            user.email,
        )
    ]


def test_successful_login_clears_failures_on_locked_connection(
    monkeypatch,
):
    password = "correct password"

    user = SimpleNamespace(
        id="user_success_rate",
        email="success@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=(
            AuthService._build_password_hash(
                password,
                iterations=(
                    AuthService.ITERATIONS
                ),
            )
        ),
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    cleared = []

    def clear_failures(
        cls,
        locked_connection,
        identifier,
    ):
        cleared.append(
            (
                locked_connection,
                identifier,
            )
        )

    def must_not_record(
        cls,
        locked_connection,
        identifier,
        now=None,
    ):
        raise AssertionError(
            "Successful login must not "
            "record a failure."
        )

    monkeypatch.setattr(
        AuthRateLimiter,
        "clear_with_connection",
        classmethod(
            clear_failures
        ),
    )

    monkeypatch.setattr(
        AuthRateLimiter,
        "record_failure_with_connection",
        classmethod(
            must_not_record
        ),
    )

    authenticated = service.authenticate(
        user.email,
        password,
    )

    assert authenticated is user

    assert cleared == [
        (
            connection,
            user.email,
        )
    ]


def test_unknown_account_records_failure_after_dummy_check(
    monkeypatch,
):
    user = SimpleNamespace(
        id="unused_user_rate",
        email="existing@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=None,
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    recorded = []

    def record_failure(
        cls,
        locked_connection,
        identifier,
        now=None,
    ):
        recorded.append(
            (
                locked_connection,
                identifier,
            )
        )

    monkeypatch.setattr(
        AuthRateLimiter,
        "record_failure_with_connection",
        classmethod(
            record_failure
        ),
    )

    authenticated = service.authenticate(
        "missing@example.com",
        "attempted password",
    )

    assert authenticated is None

    assert recorded == [
        (
            connection,
            "missing@example.com",
        )
    ]



def test_set_password_revokes_sessions_on_same_connection(
    monkeypatch,
):
    old_password = (
        "old sufficiently long password"
    )

    new_password = (
        "new sufficiently long password"
    )

    user = SimpleNamespace(
        id="user_password_change",
        email="change@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=(
            AuthService.hash_password(
                old_password
            )
        ),
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    revocations = []

    def revoke_sessions(
        locked_connection,
        user_id,
    ):
        revocations.append(
            (
                locked_connection,
                user_id,
            )
        )
        return 3

    monkeypatch.setattr(
        auth_module,
        "revoke_user_sessions_with_connection",
        revoke_sessions,
    )

    service.set_password(
        user.id,
        new_password,
    )

    assert connection.update_count == 1

    assert AuthService.verify_password(
        new_password,
        connection.password_hash,
    )

    assert revocations == [
        (
            connection,
            user.id,
        )
    ]


def test_set_password_does_not_revoke_if_user_missing(
    monkeypatch,
):
    user = SimpleNamespace(
        id="existing_user",
        email="existing@example.com",
    )

    connection = _AuthConnection(
        user_id=user.id,
        email=user.email,
        password_hash=(
            AuthService.hash_password(
                "existing sufficiently long password"
            )
        ),
    )

    _patch_auth_connection(
        monkeypatch,
        connection,
    )

    service = (
        _build_auth_service_for_test(
            user
        )
    )

    def must_not_revoke(
        locked_connection,
        user_id,
    ):
        raise AssertionError(
            "Sessions must not be revoked "
            "when the user update failed."
        )

    monkeypatch.setattr(
        auth_module,
        "revoke_user_sessions_with_connection",
        must_not_revoke,
    )

    with pytest.raises(
        ValueError,
        match="User not found",
    ):
        service.set_password(
            "missing_user",
            "another sufficiently long password",
        )

    assert connection.update_count == 0


def test_set_password_rolls_back_if_session_revocation_fails(
    monkeypatch,
):
    import sqlite3

    connection = sqlite3.connect(
        ":memory:"
    )

    connection.execute(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            password_hash TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE user_sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    user_id = "rollback_user"

    old_password = (
        "old rollback password value"
    )

    new_password = (
        "new rollback password value"
    )

    old_hash = (
        AuthService.hash_password(
            old_password
        )
    )

    connection.execute(
        """
        INSERT INTO users (
            id,
            password_hash,
            updated_at
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            old_hash,
            "before-change",
        ),
    )

    connection.execute(
        """
        INSERT INTO user_sessions (
            token,
            user_id,
            expires_at,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "existing-session",
            user_id,
            "2099-01-01T00:00:00+00:00",
            "2026-09-01T00:00:00+00:00",
        ),
    )

    connection.commit()

    @contextmanager
    def real_sqlite_connection():
        with connection:
            yield connection

    monkeypatch.setattr(
        auth_module,
        "get_connection",
        real_sqlite_connection,
    )

    def failing_revocation(
        locked_connection,
        target_user_id,
    ):
        locked_connection.execute(
            """
            DELETE FROM user_sessions
            WHERE user_id = ?
            """,
            (
                target_user_id,
            ),
        )

        raise RuntimeError(
            "simulated revocation failure"
        )

    monkeypatch.setattr(
        auth_module,
        "revoke_user_sessions_with_connection",
        failing_revocation,
    )

    service = AuthService.__new__(
        AuthService
    )

    with pytest.raises(
        RuntimeError,
        match="simulated revocation failure",
    ):
        service.set_password(
            user_id,
            new_password,
        )

    stored_user = connection.execute(
        """
        SELECT password_hash
        FROM users
        WHERE id = ?
        """,
        (
            user_id,
        ),
    ).fetchone()

    assert stored_user is not None

    assert (
        stored_user[0]
        == old_hash
    )

    assert AuthService.verify_password(
        old_password,
        stored_user[0],
    )

    assert not AuthService.verify_password(
        new_password,
        stored_user[0],
    )

    session_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM user_sessions
        WHERE user_id = ?
        """,
        (
            user_id,
        ),
    ).fetchone()[0]

    assert session_count == 1

    connection.close()
