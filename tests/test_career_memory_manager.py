from copy import deepcopy

from services.career_memory_manager import (
    CAREER_MEMORY_SCHEMA_VERSION,
    CareerMemoryManager,
)
from services.career_memory_source_builder import (
    CareerMemorySourceSnapshot,
)
from services.career_memory_repository import (
    build_memory_event_signature,
)


def _payload():
    return {
        "candidate": {
            "current_role": (
                "Operations Specialist"
            ),
        },
        "career_objective": {
            "title": (
                "Technical Operations"
            ),
        },
        "career_updates": [
            {
                "id": "update-1",
                "description": (
                    "Started SQL"
                ),
            }
        ],
        "market_evidence": {
            "sample_size": 10,
            "average_fit": 60.0,
        },
        "application_outcomes": [],
    }


class FakeRepository:
    def __init__(self):
        self.snapshot = None
        self.events = {}
        self.save_calls = 0
        self.append_calls = 0

    def get_snapshot(
        self,
        candidate_id,
    ):
        return deepcopy(
            self.snapshot
        )

    def append_event(
        self,
        *,
        candidate_id,
        event_type,
        authority,
        source_type,
        payload,
        source_ref="",
    ):
        self.append_calls += 1

        signature = (
            build_memory_event_signature(
                event_type=event_type,
                authority=authority,
                source_type=source_type,
                source_ref=source_ref,
                payload=payload,
            )
        )

        key = (
            candidate_id,
            signature,
        )

        if key in self.events:
            return False

        self.events[key] = {
            "candidate_id": candidate_id,
            "event_type": event_type,
            "authority": authority,
            "source_type": source_type,
            "source_ref": source_ref,
            "payload": deepcopy(
                payload
            ),
        }

        return True

    def save_snapshot(
        self,
        *,
        candidate_id,
        memory,
        source_signature,
        memory_schema_version,
    ):
        self.save_calls += 1

        previous_version = (
            self.snapshot.get(
                "memory_version",
                0,
            )
            if self.snapshot
            else 0
        )

        created_at = (
            self.snapshot.get(
                "created_at",
                "created",
            )
            if self.snapshot
            else "created"
        )

        self.snapshot = {
            "candidate_id": candidate_id,
            "memory_version": (
                previous_version + 1
            ),
            "memory_schema_version": (
                memory_schema_version
            ),
            "source_signature": (
                source_signature
            ),
            "memory": deepcopy(
                memory
            ),
            "created_at": created_at,
            "updated_at": (
                f"updated-{self.save_calls}"
            ),
        }

        return deepcopy(
            self.snapshot
        )


class MutableSourceBuilder:
    def __init__(
        self,
        payload,
        signature="signature-v1",
    ):
        self.payload = deepcopy(
            payload
        )
        self.signature = signature
        self.calls = 0

    def __call__(
        self,
        candidate_id,
    ):
        self.calls += 1

        return CareerMemorySourceSnapshot(
            candidate_id=candidate_id,
            payload=deepcopy(
                self.payload
            ),
            source_signature=(
                self.signature
            ),
        )


def test_first_refresh_creates_memory_v1_and_events():
    repository = FakeRepository()

    source = MutableSourceBuilder(
        _payload()
    )

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
    )

    result = manager.refresh(
        "candidate-1"
    )

    assert result["changed"] is True
    assert result["new_events"] == 5

    snapshot = result[
        "snapshot"
    ]

    assert (
        snapshot["memory_version"]
        == 1
    )

    assert (
        snapshot[
            "memory_schema_version"
        ]
        == CAREER_MEMORY_SCHEMA_VERSION
    )

    assert (
        snapshot["memory"]["facts"][
            "candidate"
        ]["current_role"]
        == "Operations Specialist"
    )

    assert (
        snapshot["memory"][
            "inferences"
        ]
        == []
    )

    assert repository.save_calls == 1


def test_same_signature_is_true_noop():
    repository = FakeRepository()

    source = MutableSourceBuilder(
        _payload()
    )

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
    )

    first = manager.refresh(
        "candidate-1"
    )

    event_count = len(
        repository.events
    )

    second = manager.refresh(
        "candidate-1"
    )

    assert first["changed"] is True
    assert second["changed"] is False

    assert (
        second["snapshot"][
            "memory_version"
        ]
        == 1
    )

    assert (
        len(repository.events)
        == event_count
    )

    assert repository.save_calls == 1

    # On NO-OP, append_event is not
    # called a second time.
    assert repository.append_calls == 5


def test_only_changed_section_creates_new_event():
    repository = FakeRepository()

    source = MutableSourceBuilder(
        _payload()
    )

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
    )

    manager.refresh(
        "candidate-1"
    )

    original_event_count = len(
        repository.events
    )

    source.payload[
        "market_evidence"
    ] = {
        "sample_size": 11,
        "average_fit": 65.0,
    }

    source.signature = (
        "signature-v2"
    )

    result = manager.refresh(
        "candidate-1"
    )

    assert result["changed"] is True
    assert result["new_events"] == 1

    assert (
        len(repository.events)
        == original_event_count + 1
    )

    assert (
        result["snapshot"][
            "memory_version"
        ]
        == 2
    )


def test_inferences_hypotheses_and_continuity_are_preserved():
    repository = FakeRepository()

    source = MutableSourceBuilder(
        _payload()
    )

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
    )

    first = manager.refresh(
        "candidate-1"
    )

    repository.snapshot[
        "memory"
    ]["inferences"] = [
        {
            "statement": (
                "Possible support preference"
            ),
            "confidence": 0.6,
        }
    ]

    repository.snapshot[
        "memory"
    ]["hypotheses"] = [
        {
            "statement": (
                "May prefer remote roles"
            ),
            "confidence": 0.4,
        }
    ]

    repository.snapshot[
        "memory"
    ]["continuity_note"] = (
        "Continue observing role preference."
    )

    source.payload[
        "career_updates"
    ].append(
        {
            "id": "update-2",
            "description": (
                "Started Python automation"
            ),
        }
    )

    source.signature = (
        "signature-v2"
    )

    second = manager.refresh(
        "candidate-1"
    )

    memory = second[
        "snapshot"
    ]["memory"]

    assert (
        memory["inferences"]
        == repository.snapshot[
            "memory"
        ]["inferences"]
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
            "Continue observing role preference."
        )
    )

    assert first["changed"] is True


def test_change_to_empty_section_is_recorded_as_delta():
    repository = FakeRepository()

    payload = _payload()

    source = MutableSourceBuilder(
        payload
    )

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
    )

    manager.refresh(
        "candidate-1"
    )

    original_event_count = len(
        repository.events
    )

    source.payload[
        "career_updates"
    ] = []

    source.signature = (
        "signature-v2"
    )

    result = manager.refresh(
        "candidate-1"
    )

    assert result["new_events"] == 1

    assert (
        len(repository.events)
        == original_event_count + 1
    )

    assert (
        result["snapshot"]["memory"][
            "facts"
        ]["career_updates"]
        == []
    )
