from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from services.database import (
    create_account_action_request_schema,
    get_connection,
    is_postgres,
)


class AccountActionRateLimiter:
    REQUEST_LIMIT = 3
    WINDOW_MINUTES = 15
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
        normalized = cls._normalize_identifier(
            identifier
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
        action: str,
        identifier: str,
    ) -> int:
        raw = (
            f"{action}:"
            f"{cls._normalize_identifier(identifier)}"
        )

        digest = hashlib.sha256(
            raw.encode("utf-8")
        ).digest()

        return int.from_bytes(
            digest[:8],
            byteorder="big",
            signed=True,
        )

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
    @contextmanager
    def _serialized_request(
        cls,
        action: str,
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
                            action,
                            identifier,
                        ),
                    ),
                )

            else:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

            create_account_action_request_schema(
                connection
            )

            yield connection

    @classmethod
    def consume(
        cls,
        action: str,
        identifier: str,
        *,
        now=None,
    ) -> bool:
        normalized_action = str(
            action or ""
        ).strip().lower()

        normalized_identifier = (
            cls._normalize_identifier(
                identifier
            )
        )

        if not normalized_action:
            raise ValueError(
                "Action is required."
            )

        if not normalized_identifier:
            raise ValueError(
                "Identifier is required."
            )

        current = cls._coerce_now(
            now
        )

        window_cutoff = (
            current
            - timedelta(
                minutes=cls.WINDOW_MINUTES
            )
        )

        retention_cutoff = (
            current
            - timedelta(
                hours=cls.RETENTION_HOURS
            )
        )

        identifier_hash = (
            cls._identifier_hash(
                normalized_identifier
            )
        )

        placeholder = (
            cls._placeholder()
        )

        with cls._serialized_request(
            normalized_action,
            normalized_identifier,
        ) as connection:
            connection.execute(
                f"""
                DELETE FROM account_action_requests
                WHERE requested_at < {placeholder}
                """,
                (
                    retention_cutoff.isoformat(),
                ),
            )

            row = connection.execute(
                f"""
                SELECT COUNT(*) AS request_count
                FROM account_action_requests
                WHERE
                    action = {placeholder}
                    AND identifier_hash = {placeholder}
                    AND requested_at >= {placeholder}
                """,
                (
                    normalized_action,
                    identifier_hash,
                    window_cutoff.isoformat(),
                ),
            ).fetchone()

            request_count = int(
                row["request_count"] or 0
            )

            if (
                request_count
                >= cls.REQUEST_LIMIT
            ):
                return False

            connection.execute(
                f"""
                INSERT INTO account_action_requests (
                    id,
                    action,
                    identifier_hash,
                    requested_at
                )
                VALUES (
                    {placeholder},
                    {placeholder},
                    {placeholder},
                    {placeholder}
                )
                """,
                (
                    f"account_action_request_{uuid4().hex}",
                    normalized_action,
                    identifier_hash,
                    current.isoformat(),
                ),
            )

            return True
