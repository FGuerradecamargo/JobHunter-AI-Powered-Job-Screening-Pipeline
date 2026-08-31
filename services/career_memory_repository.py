from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from services.database import (
    get_connection,
    initialize_database,
    utc_now,
)


VALID_MEMORY_AUTHORITIES = {
    "fact",
    "market_evidence",
    "outcome",
    "inference",
    "hypothesis",
    "continuity",
}


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _safe_json_object(
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except (
        TypeError,
        json.JSONDecodeError,
    ):
        return {}

    if not isinstance(parsed, dict):
        return {}

    return parsed


def build_memory_event_signature(
    *,
    event_type: str,
    authority: str,
    source_type: str,
    source_ref: str,
    payload: dict[str, Any],
) -> str:
    """
    Deterministic identity for one memory event.

    candidate_id is intentionally excluded because
    uniqueness is already scoped by candidate_id in DB.
    """

    canonical = _canonical_json(
        {
            "event_type": str(
                event_type or ""
            ).strip(),
            "authority": str(
                authority or ""
            ).strip(),
            "source_type": str(
                source_type or ""
            ).strip(),
            "source_ref": str(
                source_ref or ""
            ).strip(),
            "payload": payload,
        }
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


class CareerMemoryRepository:
    def __init__(self) -> None:
        initialize_database()

    def get_snapshot(
        self,
        candidate_id: str,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM candidate_career_memory
                WHERE candidate_id = %s
                """,
                (
                    candidate_id,
                ),
            ).fetchone()

        if row is None:
            return None

        item = dict(row)

        item["memory"] = _safe_json_object(
            item.pop(
                "memory_json",
                "{}",
            )
        )

        return item

    def save_snapshot(
        self,
        *,
        candidate_id: str,
        memory: dict[str, Any],
        source_signature: str,
        memory_schema_version: str,
    ) -> dict[str, Any]:
        normalized_candidate_id = str(
            candidate_id or ""
        ).strip()

        normalized_source_signature = str(
            source_signature or ""
        ).strip()

        normalized_schema_version = str(
            memory_schema_version or ""
        ).strip()

        if not normalized_candidate_id:
            raise ValueError(
                "candidate_id must be non-empty."
            )

        if not isinstance(memory, dict):
            raise ValueError(
                "memory must be a dictionary."
            )

        if not normalized_source_signature:
            raise ValueError(
                "source_signature must be non-empty."
            )

        if not normalized_schema_version:
            raise ValueError(
                "memory_schema_version must be non-empty."
            )

        now = utc_now()

        memory_json = _canonical_json(
            memory
        )

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO candidate_career_memory (
                    candidate_id,
                    memory_version,
                    memory_schema_version,
                    source_signature,
                    memory_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, 1, %s, %s, %s, %s, %s
                )

                ON CONFLICT(candidate_id)
                DO UPDATE SET
                    memory_version =
                        candidate_career_memory.memory_version + 1,
                    memory_schema_version =
                        excluded.memory_schema_version,
                    source_signature =
                        excluded.source_signature,
                    memory_json =
                        excluded.memory_json,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    normalized_candidate_id,
                    normalized_schema_version,
                    normalized_source_signature,
                    memory_json,
                    now,
                    now,
                ),
            )

        snapshot = self.get_snapshot(
            normalized_candidate_id
        )

        if snapshot is None:
            raise RuntimeError(
                "Career Memory snapshot was not persisted."
            )

        return snapshot

    def append_event(
        self,
        *,
        candidate_id: str,
        event_type: str,
        authority: str,
        source_type: str,
        payload: dict[str, Any],
        source_ref: str = "",
    ) -> bool:
        normalized_candidate_id = str(
            candidate_id or ""
        ).strip()

        normalized_event_type = str(
            event_type or ""
        ).strip()

        normalized_authority = str(
            authority or ""
        ).strip()

        normalized_source_type = str(
            source_type or ""
        ).strip()

        normalized_source_ref = str(
            source_ref or ""
        ).strip()

        if not normalized_candidate_id:
            raise ValueError(
                "candidate_id must be non-empty."
            )

        if not normalized_event_type:
            raise ValueError(
                "event_type must be non-empty."
            )

        if (
            normalized_authority
            not in VALID_MEMORY_AUTHORITIES
        ):
            raise ValueError(
                "Invalid Career Memory authority: "
                f"{normalized_authority!r}"
            )

        if not normalized_source_type:
            raise ValueError(
                "source_type must be non-empty."
            )

        if not isinstance(payload, dict):
            raise ValueError(
                "payload must be a dictionary."
            )

        event_signature = (
            build_memory_event_signature(
                event_type=normalized_event_type,
                authority=normalized_authority,
                source_type=normalized_source_type,
                source_ref=normalized_source_ref,
                payload=payload,
            )
        )

        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO candidate_career_memory_events (
                    id,
                    candidate_id,
                    event_type,
                    authority,
                    source_type,
                    source_ref,
                    event_signature,
                    payload_json,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )

                ON CONFLICT(
                    candidate_id,
                    event_signature
                )
                DO NOTHING
                """,
                (
                    "career_memory_event_"
                    + uuid4().hex,
                    normalized_candidate_id,
                    normalized_event_type,
                    normalized_authority,
                    normalized_source_type,
                    normalized_source_ref,
                    event_signature,
                    _canonical_json(
                        payload
                    ),
                    utc_now(),
                ),
            )

        return bool(
            cursor.rowcount
        )

    def list_events(
        self,
        candidate_id: str,
    ) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM candidate_career_memory_events
                WHERE candidate_id = %s
                ORDER BY
                    created_at ASC,
                    id ASC
                """,
                (
                    candidate_id,
                ),
            ).fetchall()

        results: list[
            dict[str, Any]
        ] = []

        for row in rows:
            item = dict(row)

            item["payload"] = (
                _safe_json_object(
                    item.pop(
                        "payload_json",
                        "{}",
                    )
                )
            )

            results.append(
                item
            )

        return results
