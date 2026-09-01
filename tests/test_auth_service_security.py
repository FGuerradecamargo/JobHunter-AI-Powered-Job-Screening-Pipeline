from __future__ import annotations

import hashlib
import os

import pytest

from services.auth_service import AuthService


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

    monkeypatch.setattr(
        auth_module,
        "get_connection",
        fake_get_connection,
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
