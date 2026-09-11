from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from services.database import (
    create_security_audit_schema,
    get_connection,
    utc_now,
)


class SecurityAuditRepository:
    ALLOWED_OUTCOMES = {
        "success",
        "denied",
        "error",
    }

    SENSITIVE_KEY_PARTS = {
        "authorization",
        "cookie",
        "credential",
        "password",
        "secret",
        "token",
    }

    def record(
        self,
        *,
        event_type: str,
        outcome: str,
        authenticated_user_id: str,
        active_user_id: str,
        target_type: str = "",
        target_id: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        with get_connection() as connection:
            return self.record_with_connection(
                connection,
                event_type=event_type,
                outcome=outcome,
                authenticated_user_id=(
                    authenticated_user_id
                ),
                active_user_id=active_user_id,
                target_type=target_type,
                target_id=target_id,
                metadata=metadata,
            )

    def record_with_connection(
        self,
        connection,
        *,
        event_type: str,
        outcome: str,
        authenticated_user_id: str,
        active_user_id: str,
        target_type: str = "",
        target_id: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        normalized_event_type = self._required(
            event_type,
            "Event type",
        )
        normalized_outcome = self._required(
            outcome,
            "Outcome",
        )
        normalized_authenticated_user_id = self._required(
            authenticated_user_id,
            "Authenticated user ID",
        )
        normalized_active_user_id = self._required(
            active_user_id,
            "Active user ID",
        )

        if normalized_outcome not in self.ALLOWED_OUTCOMES:
            raise ValueError("Invalid audit outcome.")

        safe_metadata = self._validate_metadata(
            metadata or {}
        )

        event_id = uuid4().hex

        create_security_audit_schema(connection)

        connection.execute(
            """
            INSERT INTO security_audit_events (
                id,
                event_type,
                outcome,
                authenticated_user_id,
                active_user_id,
                target_type,
                target_id,
                metadata_json,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                event_id,
                normalized_event_type,
                normalized_outcome,
                normalized_authenticated_user_id,
                normalized_active_user_id,
                str(target_type or "").strip(),
                str(target_id or "").strip(),
                json.dumps(
                    safe_metadata,
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                utc_now(),
            ),
        )

        return event_id

    @classmethod
    def _validate_metadata(
        cls,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(metadata, Mapping):
            raise ValueError("Audit metadata must be a mapping.")

        safe_metadata = {}

        for raw_key, value in metadata.items():
            key = str(raw_key or "").strip()
            normalized_key = key.lower()

            if not key:
                raise ValueError(
                    "Audit metadata keys cannot be empty."
                )

            if any(
                part in normalized_key
                for part in cls.SENSITIVE_KEY_PARTS
            ):
                raise ValueError(
                    "Sensitive audit metadata is not allowed."
                )

            if not isinstance(
                value,
                (str, int, float, bool, type(None)),
            ):
                raise ValueError(
                    "Audit metadata values must be scalar."
                )

            safe_metadata[key] = value

        return safe_metadata

    @staticmethod
    def _required(
        value: str,
        label: str,
    ) -> str:
        normalized = str(value or "").strip()

        if not normalized:
            raise ValueError(f"{label} is required.")

        return normalized
