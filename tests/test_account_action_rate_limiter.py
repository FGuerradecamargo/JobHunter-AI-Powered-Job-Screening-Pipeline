from datetime import datetime, timedelta, timezone

import pytest

from services.account_action_rate_limiter import (
    AccountActionRateLimiter,
)
from services.database import (
    create_account_action_request_schema,
    get_connection,
)


@pytest.fixture(autouse=True)
def clear_rate_limit_table():
    with get_connection() as connection:
        create_account_action_request_schema(
            connection
        )
        connection.execute(
            """
            DELETE FROM account_action_requests
            """
        )

    yield

    with get_connection() as connection:
        create_account_action_request_schema(
            connection
        )
        connection.execute(
            """
            DELETE FROM account_action_requests
            """
        )


def test_allows_requests_below_limit():
    now = datetime(
        2026,
        9,
        4,
        7,
        30,
        tzinfo=timezone.utc,
    )

    assert (
        AccountActionRateLimiter.consume(
            "password_reset_request",
            "test@example.com",
            now=now,
        )
        is True
    )

    assert (
        AccountActionRateLimiter.consume(
            "password_reset_request",
            "test@example.com",
            now=now + timedelta(seconds=1),
        )
        is True
    )

    assert (
        AccountActionRateLimiter.consume(
            "password_reset_request",
            "test@example.com",
            now=now + timedelta(seconds=2),
        )
        is True
    )


def test_blocks_request_after_limit():
    now = datetime(
        2026,
        9,
        4,
        7,
        30,
        tzinfo=timezone.utc,
    )

    for offset in range(
        AccountActionRateLimiter.REQUEST_LIMIT
    ):
        assert (
            AccountActionRateLimiter.consume(
                "password_reset_request",
                "test@example.com",
                now=now + timedelta(seconds=offset),
            )
            is True
        )

    assert (
        AccountActionRateLimiter.consume(
            "password_reset_request",
            "test@example.com",
            now=now + timedelta(seconds=10),
        )
        is False
    )


def test_actions_are_isolated():
    now = datetime(
        2026,
        9,
        4,
        7,
        30,
        tzinfo=timezone.utc,
    )

    for offset in range(
        AccountActionRateLimiter.REQUEST_LIMIT
    ):
        assert (
            AccountActionRateLimiter.consume(
                "password_reset_request",
                "test@example.com",
                now=now + timedelta(seconds=offset),
            )
            is True
        )

    assert (
        AccountActionRateLimiter.consume(
            "email_verification_resend",
            "test@example.com",
            now=now + timedelta(seconds=10),
        )
        is True
    )


def test_identifier_is_case_insensitive():
    now = datetime(
        2026,
        9,
        4,
        7,
        30,
        tzinfo=timezone.utc,
    )

    for offset in range(
        AccountActionRateLimiter.REQUEST_LIMIT
    ):
        assert (
            AccountActionRateLimiter.consume(
                "password_reset_request",
                "Test@Example.com",
                now=now + timedelta(seconds=offset),
            )
            is True
        )

    assert (
        AccountActionRateLimiter.consume(
            "password_reset_request",
            "test@example.com",
            now=now + timedelta(seconds=10),
        )
        is False
    )


def test_window_expires():
    now = datetime(
        2026,
        9,
        4,
        7,
        30,
        tzinfo=timezone.utc,
    )

    for offset in range(
        AccountActionRateLimiter.REQUEST_LIMIT
    ):
        assert (
            AccountActionRateLimiter.consume(
                "password_reset_request",
                "test@example.com",
                now=now + timedelta(seconds=offset),
            )
            is True
        )

    assert (
        AccountActionRateLimiter.consume(
            "password_reset_request",
            "test@example.com",
            now=(
                now
                + timedelta(
                    minutes=(
                        AccountActionRateLimiter
                        .WINDOW_MINUTES
                        + 1
                    )
                )
            ),
        )
        is True
    )
