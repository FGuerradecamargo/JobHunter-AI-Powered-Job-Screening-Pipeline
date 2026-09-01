from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

import services.auth_rate_limiter as limiter_module
from services.auth_rate_limiter import (
    AuthRateLimiter,
)


@pytest.fixture
def rate_limiter_db(
    monkeypatch,
):
    connection = sqlite3.connect(
        ":memory:"
    )
    connection.row_factory = (
        sqlite3.Row
    )

    @contextmanager
    def fake_get_connection():
        with connection:
            yield connection

    monkeypatch.setattr(
        limiter_module,
        "get_connection",
        fake_get_connection,
    )

    monkeypatch.setattr(
        limiter_module,
        "is_postgres",
        lambda: False,
    )

    yield connection

    connection.close()


def _now():
    return datetime(
        2026,
        9,
        1,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


def test_identifier_is_normalized_before_hashing():
    first = (
        AuthRateLimiter
        ._identifier_hash(
            " User@Example.com "
        )
    )

    second = (
        AuthRateLimiter
        ._identifier_hash(
            "user@example.com"
        )
    )

    assert first == second
    assert len(first) == 64


def test_email_is_not_stored_in_plaintext(
    rate_limiter_db,
):
    email = "private@example.com"

    AuthRateLimiter.record_failure(
        email,
        now=_now(),
    )

    row = rate_limiter_db.execute(
        """
        SELECT
            identifier_hash
        FROM auth_login_failures
        """
    ).fetchone()

    assert row is not None
    assert row["identifier_hash"] != email
    assert "private@example.com" not in (
        row["identifier_hash"]
    )


def test_first_four_failures_are_not_limited(
    rate_limiter_db,
):
    email = "user@example.com"
    now = _now()

    for index in range(4):
        AuthRateLimiter.record_failure(
            email,
            now=(
                now
                + timedelta(
                    seconds=index
                )
            ),
        )

    assert not AuthRateLimiter.is_limited(
        email,
        now=(
            now
            + timedelta(
                seconds=4
            )
        ),
    )


def test_fifth_failure_triggers_one_minute_block(
    rate_limiter_db,
):
    email = "user@example.com"
    now = _now()

    for index in range(5):
        AuthRateLimiter.record_failure(
            email,
            now=(
                now
                + timedelta(
                    seconds=index
                )
            ),
        )

    fifth_attempt_time = (
        now
        + timedelta(seconds=4)
    )

    assert AuthRateLimiter.is_limited(
        email,
        now=(
            fifth_attempt_time
            + timedelta(
                seconds=59
            )
        ),
    )

    assert not AuthRateLimiter.is_limited(
        email,
        now=(
            fifth_attempt_time
            + timedelta(
                seconds=60
            )
        ),
    )


def test_sixth_failure_doubles_block_duration(
    rate_limiter_db,
):
    email = "user@example.com"
    now = _now()

    for index in range(5):
        AuthRateLimiter.record_failure(
            email,
            now=(
                now
                + timedelta(
                    seconds=index
                )
            ),
        )

    sixth_time = (
        now
        + timedelta(
            seconds=65
        )
    )

    assert not AuthRateLimiter.is_limited(
        email,
        now=sixth_time,
    )

    AuthRateLimiter.record_failure(
        email,
        now=sixth_time,
    )

    assert AuthRateLimiter.is_limited(
        email,
        now=(
            sixth_time
            + timedelta(
                seconds=119
            )
        ),
    )

    assert not AuthRateLimiter.is_limited(
        email,
        now=(
            sixth_time
            + timedelta(
                seconds=120
            )
        ),
    )


def test_failures_outside_window_do_not_limit(
    rate_limiter_db,
):
    email = "user@example.com"
    now = _now()

    for index in range(5):
        AuthRateLimiter.record_failure(
            email,
            now=(
                now
                + timedelta(
                    seconds=index
                )
            ),
        )

    assert not AuthRateLimiter.is_limited(
        email,
        now=(
            now
            + timedelta(
                minutes=16
            )
        ),
    )


def test_clear_removes_identifier_failures(
    rate_limiter_db,
):
    email = "user@example.com"
    now = _now()

    for index in range(5):
        AuthRateLimiter.record_failure(
            email,
            now=(
                now
                + timedelta(
                    seconds=index
                )
            ),
        )

    assert AuthRateLimiter.is_limited(
        email,
        now=(
            now
            + timedelta(
                seconds=5
            )
        ),
    )

    AuthRateLimiter.clear(
        email
    )

    assert not AuthRateLimiter.is_limited(
        email,
        now=(
            now
            + timedelta(
                seconds=5
            )
        ),
    )

    row = rate_limiter_db.execute(
        """
        SELECT COUNT(*) AS total
        FROM auth_login_failures
        """
    ).fetchone()

    assert row["total"] == 0


def test_failures_are_isolated_per_identifier(
    rate_limiter_db,
):
    now = _now()

    for index in range(5):
        AuthRateLimiter.record_failure(
            "first@example.com",
            now=(
                now
                + timedelta(
                    seconds=index
                )
            ),
        )

    assert AuthRateLimiter.is_limited(
        "first@example.com",
        now=(
            now
            + timedelta(
                seconds=5
            )
        ),
    )

    assert not AuthRateLimiter.is_limited(
        "second@example.com",
        now=(
            now
            + timedelta(
                seconds=5
            )
        ),
    )


def test_lock_key_is_deterministic_and_normalized():
    first = AuthRateLimiter._lock_key(
        " User@Example.com "
    )

    second = AuthRateLimiter._lock_key(
        "user@example.com"
    )

    assert first == second
    assert isinstance(first, int)


def test_different_identifiers_use_different_lock_keys():
    first = AuthRateLimiter._lock_key(
        "first@example.com"
    )

    second = AuthRateLimiter._lock_key(
        "second@example.com"
    )

    assert first != second


def test_postgres_serialized_attempt_uses_advisory_lock(
    monkeypatch,
):
    class FakeConnection:
        def __init__(self):
            self.calls = []

        def execute(
            self,
            sql,
            params=None,
        ):
            normalized = " ".join(
                sql.split()
            )

            self.calls.append(
                (
                    normalized,
                    params,
                )
            )

            return None

    connection = FakeConnection()

    @contextmanager
    def fake_get_connection():
        yield connection

    monkeypatch.setattr(
        limiter_module,
        "get_connection",
        fake_get_connection,
    )

    monkeypatch.setattr(
        limiter_module,
        "is_postgres",
        lambda: True,
    )

    email = "user@example.com"

    with AuthRateLimiter.serialized_attempt(
        email
    ) as yielded_connection:
        assert (
            yielded_connection
            is connection
        )

    lock_calls = [
        call
        for call in connection.calls
        if (
            "pg_advisory_xact_lock"
            in call[0]
        )
    ]

    assert len(lock_calls) == 1

    _, params = lock_calls[0]

    assert params == (
        AuthRateLimiter._lock_key(
            email
        ),
    )


def test_serialized_attempt_reuses_one_connection(
    monkeypatch,
):
    connection = sqlite3.connect(
        ":memory:"
    )
    connection.row_factory = (
        sqlite3.Row
    )

    connection_count = 0

    @contextmanager
    def fake_get_connection():
        nonlocal connection_count
        connection_count += 1

        with connection:
            yield connection

    monkeypatch.setattr(
        limiter_module,
        "get_connection",
        fake_get_connection,
    )

    monkeypatch.setattr(
        limiter_module,
        "is_postgres",
        lambda: False,
    )

    email = "atomic@example.com"
    now = _now()

    with AuthRateLimiter.serialized_attempt(
        email
    ) as locked_connection:
        for index in range(5):
            (
                AuthRateLimiter
                .record_failure_with_connection(
                    locked_connection,
                    email,
                    now=(
                        now
                        + timedelta(
                            seconds=index
                        )
                    ),
                )
            )

        assert (
            AuthRateLimiter
            .is_limited_with_connection(
                locked_connection,
                email,
                now=(
                    now
                    + timedelta(
                        seconds=5
                    )
                ),
            )
        )

        (
            AuthRateLimiter
            .clear_with_connection(
                locked_connection,
                email,
            )
        )

        assert not (
            AuthRateLimiter
            .is_limited_with_connection(
                locked_connection,
                email,
                now=(
                    now
                    + timedelta(
                        seconds=5
                    )
                ),
            )
        )

    assert connection_count == 1

    connection.close()
