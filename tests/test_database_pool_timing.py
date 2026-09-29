import logging
from pathlib import Path

import pytest

import services.database as database


def test_postgres_pool_uses_timed_health_check():
    source = Path(
        "services/database.py"
    ).read_text(
        encoding="utf-8"
    )

    pool_start = source.index(
        "def _get_postgres_pool("
    )

    connection_start = source.index(
        "@contextmanager\ndef get_connection",
        pool_start,
    )

    pool_block = source[
        pool_start:
        connection_start
    ]

    assert (
        "check=_check_postgres_connection"
        in pool_block
    )


def test_postgres_health_check_is_timed(
    monkeypatch,
    caplog,
):
    marker = object()
    calls = []

    monkeypatch.setattr(
        database.ConnectionPool,
        "check_connection",
        staticmethod(
            lambda connection: calls.append(
                connection
            )
        ),
    )

    with caplog.at_level(
        logging.INFO,
        logger="workpilot.timing",
    ):
        database._check_postgres_connection(
            marker
        )

    assert calls == [
        marker
    ]

    assert (
        "block=database.pool.check"
        in caplog.text
    )

    assert (
        "outcome=ok"
        in caplog.text
    )


def test_postgres_checkout_is_timed_without_changing_context_semantics(
    monkeypatch,
    caplog,
):
    events = []
    raw_connection = object()

    class ConnectionContext:
        def __enter__(
            self,
        ):
            events.append(
                "enter"
            )

            return raw_connection

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            events.append(
                "exit"
            )

            return False

    class Pool:
        def connection(
            self,
        ):
            events.append(
                "connection"
            )

            return ConnectionContext()

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://example.invalid/db",
    )

    monkeypatch.setattr(
        database,
        "_get_postgres_pool",
        lambda database_url: Pool(),
    )

    with caplog.at_level(
        logging.INFO,
        logger="workpilot.timing",
    ):
        with database.get_connection() as connection:
            assert isinstance(
                connection,
                database.TimedConnection,
            )

            events.append(
                "body"
            )

    assert events == [
        "connection",
        "enter",
        "body",
        "exit",
    ]

    assert (
        "block=database.pool.checkout"
        in caplog.text
    )

    assert (
        "outcome=ok"
        in caplog.text
    )


def test_failed_postgres_checkout_is_timed_and_propagated(
    monkeypatch,
    caplog,
):
    class ConnectionContext:
        def __enter__(
            self,
        ):
            raise RuntimeError(
                "checkout failed"
            )

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

    class Pool:
        def connection(
            self,
        ):
            return ConnectionContext()

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://example.invalid/db",
    )

    monkeypatch.setattr(
        database,
        "_get_postgres_pool",
        lambda database_url: Pool(),
    )

    with caplog.at_level(
        logging.INFO,
        logger="workpilot.timing",
    ):
        with pytest.raises(
            RuntimeError,
            match="checkout failed",
        ):
            with database.get_connection():
                pass

    assert (
        "block=database.pool.checkout"
        in caplog.text
    )

    assert (
        "outcome=failed"
        in caplog.text
    )
