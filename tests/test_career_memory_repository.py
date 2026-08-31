from uuid import uuid4

import pytest

from services.career_memory_repository import (
    CareerMemoryRepository,
    build_memory_event_signature,
)
from services.database import (
    get_connection,
)


def _create_temp_candidate() -> str:
    candidate_id = (
        "career_memory_repo_test_"
        + uuid4().hex
    )

    with get_connection() as connection:
        source = connection.execute(
            """
            SELECT id
            FROM candidates
            LIMIT 1
            """
        ).fetchone()

        if source is None:
            raise RuntimeError(
                "No candidate available for test."
            )

        columns = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE
                table_schema = current_schema()
                AND table_name = 'candidates'
            ORDER BY ordinal_position
            """
        ).fetchall()

        column_names = [
            row["column_name"]
            for row in columns
        ]

        quoted_columns = ", ".join(
            f'"{name}"'
            for name in column_names
        )

        select_parts = [
            (
                "%s"
                if name == "id"
                else f'"{name}"'
            )
            for name in column_names
        ]

        connection.execute(
            f"""
            INSERT INTO candidates (
                {quoted_columns}
            )
            SELECT
                {", ".join(select_parts)}
            FROM candidates
            WHERE id = %s
            """,
            (
                candidate_id,
                source["id"],
            ),
        )

    return candidate_id


def _delete_temp_candidate(
    candidate_id: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM candidates
            WHERE id = %s
            """,
            (
                candidate_id,
            ),
        )


def test_snapshot_versions_increment_and_created_at_is_preserved():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        first = repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "current_positioning": "first",
            },
            source_signature="source-v1",
            memory_schema_version="career-memory-v1",
        )

        assert first["memory_version"] == 1
        assert (
            first["memory"][
                "current_positioning"
            ]
            == "first"
        )

        original_created_at = (
            first["created_at"]
        )

        second = repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "current_positioning": "second",
            },
            source_signature="source-v2",
            memory_schema_version="career-memory-v1",
        )

        assert second["memory_version"] == 2
        assert (
            second["created_at"]
            == original_created_at
        )
        assert (
            second["memory"][
                "current_positioning"
            ]
            == "second"
        )
        assert (
            second["source_signature"]
            == "source-v2"
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_event_signature_is_deterministic():
    payload_a = {
        "b": 2,
        "a": 1,
    }

    payload_b = {
        "a": 1,
        "b": 2,
    }

    first = build_memory_event_signature(
        event_type="career_update",
        authority="fact",
        source_type="career_update",
        source_ref="update-1",
        payload=payload_a,
    )

    second = build_memory_event_signature(
        event_type="career_update",
        authority="fact",
        source_type="career_update",
        source_ref="update-1",
        payload=payload_b,
    )

    assert first == second


def test_append_event_is_idempotent():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        kwargs = {
            "candidate_id": candidate_id,
            "event_type": "career_update",
            "authority": "fact",
            "source_type": (
                "candidate_career_updates"
            ),
            "source_ref": "update-test",
            "payload": {
                "description": "Test update",
            },
        }

        assert (
            repository.append_event(
                **kwargs
            )
            is True
        )

        assert (
            repository.append_event(
                **kwargs
            )
            is False
        )

        events = repository.list_events(
            candidate_id
        )

        assert len(events) == 1
        assert (
            events[0]["authority"]
            == "fact"
        )
        assert (
            events[0]["payload"][
                "description"
            ]
            == "Test update"
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_invalid_authority_fails_before_database():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        with pytest.raises(
            ValueError
        ):
            repository.append_event(
                candidate_id=candidate_id,
                event_type="test",
                authority="promoted_fact",
                source_type="test",
                payload={},
            )

        assert (
            repository.list_events(
                candidate_id
            )
            == []
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_snapshot_json_parse_is_safe():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "value": "valid",
            },
            source_signature="source",
            memory_schema_version="career-memory-v1",
        )

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE candidate_career_memory
                SET memory_json = %s
                WHERE candidate_id = %s
                """,
                (
                    "{not-valid-json",
                    candidate_id,
                ),
            )

        snapshot = repository.get_snapshot(
            candidate_id
        )

        assert snapshot is not None
        assert snapshot["memory"] == {}

    finally:
        _delete_temp_candidate(
            candidate_id
        )
