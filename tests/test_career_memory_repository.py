from uuid import uuid4

import pytest

from services.career_memory_repository import (
    CareerMemoryRepository,
    StaleCareerMemoryInterpretationError,
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



def test_interpretation_updates_only_low_authority_memory():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        first = repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {
                    "candidate": {
                        "current_role": "Role A",
                    },
                },
                "market_evidence": {
                    "sample_size": 10,
                },
                "outcomes": [
                    {
                        "job_id": "job-1",
                        "status": "applied",
                    }
                ],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="source-v1",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        assert first["memory_version"] == 1
        assert (
            first[
                "interpreted_source_signature"
            ]
            == ""
        )

        interpreted = (
            repository.apply_interpretation(
                candidate_id=candidate_id,
                source_signature="source-v1",
                interpretation={
                    "inferences": [
                        {
                            "statement": (
                                "Possible technical "
                                "direction."
                            ),
                            "confidence": 70,
                            "evidence_refs": [
                                "fact:test"
                            ],
                        }
                    ],
                    "hypotheses": [
                        {
                            "statement": (
                                "May prefer more "
                                "technical work."
                            ),
                            "confidence": 40,
                            "evidence_refs": [
                                "fact:test"
                            ],
                        }
                    ],
                    "continuity_note": (
                        "Watch technical-role evidence."
                    ),
                },
            )
        )

        # Interpretation completes the same
        # professional memory version.
        assert (
            interpreted[
                "memory_version"
            ]
            == 1
        )

        assert (
            interpreted[
                "interpreted_source_signature"
            ]
            == "source-v1"
        )

        memory = interpreted["memory"]

        # Authoritative layers survive untouched.
        assert (
            memory["facts"]["candidate"][
                "current_role"
            ]
            == "Role A"
        )

        assert (
            memory["market_evidence"][
                "sample_size"
            ]
            == 10
        )

        assert (
            memory["outcomes"][0][
                "job_id"
            ]
            == "job-1"
        )

        assert len(
            memory["inferences"]
        ) == 1

        assert len(
            memory["hypotheses"]
        ) == 1

        assert (
            memory["continuity_note"]
            == (
                "Watch technical-role evidence."
            )
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_new_source_keeps_previous_interpreted_signature_pending():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {},
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="source-v1",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        repository.apply_interpretation(
            candidate_id=candidate_id,
            source_signature="source-v1",
            interpretation={
                "inferences": [],
                "hypotheses": [],
                "continuity_note": (
                    "Version one interpreted."
                ),
            },
        )

        second = repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {
                    "candidate": {
                        "current_role": "Role B",
                    },
                },
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": (
                    "Version one interpreted."
                ),
            },
            source_signature="source-v2",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        assert second["memory_version"] == 2

        assert (
            second["source_signature"]
            == "source-v2"
        )

        # The pointer deliberately remains on
        # the last successfully interpreted source.
        assert (
            second[
                "interpreted_source_signature"
            ]
            == "source-v1"
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_stale_interpretation_is_rejected():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {},
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="source-v2",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        with pytest.raises(
            StaleCareerMemoryInterpretationError
        ):
            repository.apply_interpretation(
                candidate_id=candidate_id,
                source_signature="source-v1",
                interpretation={
                    "inferences": [
                        {
                            "statement": "Stale",
                        }
                    ],
                    "hypotheses": [],
                    "continuity_note": "Stale",
                },
            )

        snapshot = repository.get_snapshot(
            candidate_id
        )

        assert snapshot is not None

        assert (
            snapshot[
                "interpreted_source_signature"
            ]
            == ""
        )

        assert (
            snapshot["memory"][
                "inferences"
            ]
            == []
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_same_source_interpretation_is_idempotent():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {},
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="source-v1",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        first = repository.apply_interpretation(
            candidate_id=candidate_id,
            source_signature="source-v1",
            interpretation={
                "inferences": [
                    {
                        "statement": "First result",
                    }
                ],
                "hypotheses": [],
                "continuity_note": "First note",
            },
        )

        second = repository.apply_interpretation(
            candidate_id=candidate_id,
            source_signature="source-v1",
            interpretation={
                "inferences": [
                    {
                        "statement": (
                            "Different later result"
                        ),
                    }
                ],
                "hypotheses": [],
                "continuity_note": (
                    "Different later note"
                ),
            },
        )

        assert (
            second["memory_version"]
            == first["memory_version"]
            == 1
        )

        # Once this exact source is interpreted,
        # a later LLM response cannot rewrite it.
        assert (
            second["memory"][
                "inferences"
            ][0]["statement"]
            == "First result"
        )

        assert (
            second["memory"][
                "continuity_note"
            ]
            == "First note"
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_interpretation_persists_low_authority_events_with_provenance():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {
                    "candidate": {
                        "current_role": "Role A",
                    },
                },
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="source-events-v1",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        repository.apply_interpretation(
            candidate_id=candidate_id,
            source_signature="source-events-v1",
            interpretation={
                "inferences": [
                    {
                        "statement": (
                            "Technical work may be "
                            "a strong direction."
                        ),
                        "confidence": 70,
                        "evidence_refs": [
                            "fact:test",
                        ],
                    },
                ],
                "hypotheses": [
                    {
                        "statement": (
                            "May prefer deeper "
                            "technical ownership."
                        ),
                        "confidence": 45,
                        "evidence_refs": [
                            "fact:test",
                        ],
                    },
                ],
                "continuity_note": (
                    "Watch technical-role evidence."
                ),
            },
        )

        events = repository.list_events(
            candidate_id
        )

        interpretation_events = [
            event
            for event in events
            if event["source_type"]
            == "career_memory_ai_interpretation"
        ]

        assert len(
            interpretation_events
        ) == 3

        assert {
            event["authority"]
            for event in interpretation_events
        } == {
            "inference",
            "hypothesis",
            "continuity",
        }

        assert {
            event["source_ref"]
            for event in interpretation_events
        } == {
            "source-events-v1",
        }

        by_authority = {
            event["authority"]: event
            for event in interpretation_events
        }

        assert (
            by_authority[
                "inference"
            ]["event_type"]
            == "career_memory_inference"
        )

        assert (
            by_authority[
                "hypothesis"
            ]["event_type"]
            == "career_memory_hypothesis"
        )

        assert (
            by_authority[
                "continuity"
            ]["event_type"]
            == "career_memory_continuity"
        )

        assert (
            by_authority[
                "inference"
            ]["payload"]["confidence"]
            == 70
        )

        assert (
            by_authority[
                "continuity"
            ]["payload"]["statement"]
            == "Watch technical-role evidence."
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_interpretation_event_failure_rolls_back_snapshot_and_events(
    monkeypatch,
):
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {},
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="source-rollback-v1",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        original_append = (
            repository
            ._append_event_on_connection
        )

        calls = {
            "count": 0,
        }

        def fail_after_first_insert(
            connection,
            **kwargs,
        ):
            inserted = original_append(
                connection,
                **kwargs,
            )

            calls["count"] += 1

            if calls["count"] == 1:
                raise RuntimeError(
                    "simulated interpretation "
                    "event failure"
                )

            return inserted

        monkeypatch.setattr(
            repository,
            "_append_event_on_connection",
            fail_after_first_insert,
        )

        with pytest.raises(
            RuntimeError,
            match=(
                "simulated interpretation "
                "event failure"
            ),
        ):
            repository.apply_interpretation(
                candidate_id=candidate_id,
                source_signature=(
                    "source-rollback-v1"
                ),
                interpretation={
                    "inferences": [
                        {
                            "statement": (
                                "Must roll back."
                            ),
                        },
                    ],
                    "hypotheses": [
                        {
                            "statement": (
                                "Must also roll back."
                            ),
                        },
                    ],
                    "continuity_note": (
                        "Must not persist."
                    ),
                },
            )

        snapshot = repository.get_snapshot(
            candidate_id
        )

        assert snapshot is not None

        assert (
            snapshot[
                "interpreted_source_signature"
            ]
            == ""
        )

        assert (
            snapshot["memory"]["inferences"]
            == []
        )

        assert (
            snapshot["memory"]["hypotheses"]
            == []
        )

        assert (
            snapshot["memory"][
                "continuity_note"
            ]
            == ""
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


def test_same_source_interpretation_does_not_duplicate_events():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {},
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="source-idempotent-events",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        repository.apply_interpretation(
            candidate_id=candidate_id,
            source_signature=(
                "source-idempotent-events"
            ),
            interpretation={
                "inferences": [
                    {
                        "statement": "First inference",
                    },
                ],
                "hypotheses": [],
                "continuity_note": "First note",
            },
        )

        first_events = (
            repository.list_events(
                candidate_id
            )
        )

        first_signatures = {
            event["event_signature"]
            for event in first_events
        }

        second = repository.apply_interpretation(
            candidate_id=candidate_id,
            source_signature=(
                "source-idempotent-events"
            ),
            interpretation={
                "inferences": [
                    {
                        "statement": (
                            "Later nondeterministic "
                            "inference"
                        ),
                    },
                ],
                "hypotheses": [],
                "continuity_note": (
                    "Later nondeterministic note"
                ),
            },
        )

        second_events = (
            repository.list_events(
                candidate_id
            )
        )

        assert len(
            second_events
        ) == len(
            first_events
        )

        assert {
            event["event_signature"]
            for event in second_events
        } == first_signatures

        assert (
            second["memory"][
                "inferences"
            ][0]["statement"]
            == "First inference"
        )

        assert (
            second["memory"][
                "continuity_note"
            ]
            == "First note"
        )

    finally:
        _delete_temp_candidate(
            candidate_id
        )


def test_stale_interpretation_creates_no_interpretation_events():
    repository = CareerMemoryRepository()
    candidate_id = _create_temp_candidate()

    try:
        repository.save_snapshot(
            candidate_id=candidate_id,
            memory={
                "facts": {},
                "market_evidence": {},
                "outcomes": [],
                "inferences": [],
                "hypotheses": [],
                "continuity_note": "",
            },
            source_signature="current-source",
            memory_schema_version=(
                "career-memory-v1"
            ),
        )

        with pytest.raises(
            StaleCareerMemoryInterpretationError
        ):
            repository.apply_interpretation(
                candidate_id=candidate_id,
                source_signature="stale-source",
                interpretation={
                    "inferences": [
                        {
                            "statement": "Stale",
                        },
                    ],
                    "hypotheses": [],
                    "continuity_note": (
                        "Stale note"
                    ),
                },
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
