from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from services.database import (
    create_auth_login_failure_schema,
    get_connection,
    is_postgres,
)


class AuthRateLimiter:
    FAILURE_THRESHOLD = 5
    WINDOW_MINUTES = 15

    BASE_BLOCK_SECONDS = 60
    MAX_BLOCK_SECONDS = 15 * 60

    RETENTION_HOURS = 24

    @classmethod
    def _normalize_identifier(
        cls,
        identifier: str,
    ) -> str:
        return str(
            identifier or ""
        ).strip().lower()

    @classmethod
    def _identifier_hash(
        cls,
        identifier: str,
    ) -> str:
        normalized = (
            cls._normalize_identifier(
                identifier
            )
        )

        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    @classmethod
    def _placeholder(cls) -> str:
        if is_postgres():
            return "%s"

        return "?"

    @classmethod
    def _lock_key(
        cls,
        identifier: str,
    ) -> int:
        digest = hashlib.sha256(
            cls._normalize_identifier(
                identifier
            ).encode("utf-8")
        ).digest()

        return int.from_bytes(
            digest[:8],
            byteorder="big",
            signed=True,
        )

    @classmethod
    @contextmanager
    def serialized_attempt(
        cls,
        identifier: str,
    ):
        with get_connection() as connection:
            if is_postgres():
                connection.execute(
                    """
                    SELECT pg_advisory_xact_lock(%s)
                    """,
                    (
                        cls._lock_key(
                            identifier
                        ),
                    ),
                )

            else:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

            cls._ensure_table(
                connection
            )

            yield connection

    @classmethod
    def _coerce_now(
        cls,
        value=None,
    ) -> datetime:
        if value is None:
            return datetime.now(
                timezone.utc
            )

        if isinstance(
            value,
            datetime,
        ):
            result = value

        else:
            result = datetime.fromisoformat(
                str(value)
            )

        if result.tzinfo is None:
            result = result.replace(
                tzinfo=timezone.utc
            )

        return result.astimezone(
            timezone.utc
        )

    @classmethod
    def _ensure_table(
        cls,
        connection,
    ) -> None:
        create_auth_login_failure_schema(
            connection
        )

    @classmethod
    def is_limited_with_connection(
        cls,
        connection,
        identifier: str,
        *,
        now=None,
    ) -> bool:
        current = cls._coerce_now(
            now
        )

        window_cutoff = (
            current
            - timedelta(
                minutes=cls.WINDOW_MINUTES
            )
        )

        identifier_hash = (
            cls._identifier_hash(
                identifier
            )
        )

        placeholder = (
            cls._placeholder()
        )

        cls._ensure_table(
            connection
        )

        row = connection.execute(
            f"""
            SELECT
                COUNT(*) AS failure_count,
                MAX(attempted_at)
                    AS last_attempt_at
            FROM auth_login_failures
            WHERE
                identifier_hash = {placeholder}
                AND attempted_at >= {placeholder}
            """,
            (
                identifier_hash,
                window_cutoff.isoformat(),
            ),
        ).fetchone()

        failure_count = int(
            row["failure_count"] or 0
        )

        if (
            failure_count
            < cls.FAILURE_THRESHOLD
        ):
            return False

        last_attempt_text = row[
            "last_attempt_at"
        ]

        if not last_attempt_text:
            return False

        last_attempt = cls._coerce_now(
            last_attempt_text
        )

        exponent = max(
            failure_count
            - cls.FAILURE_THRESHOLD,
            0,
        )

        block_seconds = min(
            cls.BASE_BLOCK_SECONDS
            * (2 ** exponent),
            cls.MAX_BLOCK_SECONDS,
        )

        blocked_until = (
            last_attempt
            + timedelta(
                seconds=block_seconds
            )
        )

        return current < blocked_until

    @classmethod
    def is_limited(
        cls,
        identifier: str,
        *,
        now=None,
    ) -> bool:
        with get_connection() as connection:
            return cls.is_limited_with_connection(
                connection,
                identifier,
                now=now,
            )

    @classmethod
    def record_failure_with_connection(
        cls,
        connection,
        identifier: str,
        *,
        now=None,
    ) -> None:
        current = cls._coerce_now(
            now
        )

        retention_cutoff = (
            current
            - timedelta(
                hours=cls.RETENTION_HOURS
            )
        )

        identifier_hash = (
            cls._identifier_hash(
                identifier
            )
        )

        placeholder = (
            cls._placeholder()
        )

        cls._ensure_table(
            connection
        )

        connection.execute(
            f"""
            DELETE FROM auth_login_failures
            WHERE attempted_at < {placeholder}
            """,
            (
                retention_cutoff.isoformat(),
            ),
        )

        connection.execute(
            f"""
            INSERT INTO auth_login_failures (
                id,
                identifier_hash,
                attempted_at
            )
            VALUES (
                {placeholder},
                {placeholder},
                {placeholder}
            )
            """,
            (
                f"login_failure_{uuid4().hex}",
                identifier_hash,
                current.isoformat(),
            ),
        )

    @classmethod
    def record_failure(
        cls,
        identifier: str,
        *,
        now=None,
    ) -> None:
        with get_connection() as connection:
            cls.record_failure_with_connection(
                connection,
                identifier,
                now=now,
            )

    @classmethod
    def clear_with_connection(
        cls,
        connection,
        identifier: str,
    ) -> None:
        identifier_hash = (
            cls._identifier_hash(
                identifier
            )
        )

        placeholder = (
            cls._placeholder()
        )

        cls._ensure_table(
            connection
        )

        connection.execute(
            f"""
            DELETE FROM auth_login_failures
            WHERE identifier_hash = {placeholder}
            """,
            (
                identifier_hash,
            ),
        )

    @classmethod
    def clear(
        cls,
        identifier: str,
    ) -> None:
        with get_connection() as connection:
            cls.clear_with_connection(
                connection,
                identifier,
            )
