from copy import deepcopy

from services.career_memory_manager import (
    CAREER_MEMORY_SCHEMA_VERSION,
    CareerMemoryManager,
)
from services.career_memory_source_builder import (
    CareerMemorySourceSnapshot,
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
        "career_updates": [],
        "market_evidence": {
            "sample_size": 10,
        },
        "application_outcomes": [],
    }


class FakeRepository:
    def __init__(self):
        self.snapshot = None
        self.events = []
        self.save_calls = 0
        self.apply_calls = 0

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
        self.events.append(
            {
                "candidate_id": candidate_id,
                "event_type": event_type,
                "authority": authority,
                "source_type": source_type,
                "source_ref": source_ref,
                "payload": deepcopy(
                    payload
                ),
            }
        )

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
            self.snapshot[
                "memory_version"
            ]
            if self.snapshot
            else 0
        )

        previous_interpreted = (
            self.snapshot.get(
                "interpreted_source_signature",
                "",
            )
            if self.snapshot
            else ""
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
            "interpreted_source_signature": (
                previous_interpreted
            ),
            "memory": deepcopy(
                memory
            ),
            "created_at": "created",
            "updated_at": (
                f"saved-{self.save_calls}"
            ),
        }

        return deepcopy(
            self.snapshot
        )

    def apply_interpretation(
        self,
        *,
        candidate_id,
        source_signature,
        interpretation,
    ):
        self.apply_calls += 1

        if (
            self.snapshot[
                "source_signature"
            ]
            != source_signature
        ):
            raise RuntimeError(
                "stale interpretation"
            )

        if (
            self.snapshot[
                "interpreted_source_signature"
            ]
            == source_signature
        ):
            return deepcopy(
                self.snapshot
            )

        memory = self.snapshot[
            "memory"
        ]

        memory["inferences"] = deepcopy(
            interpretation[
                "inferences"
            ]
        )

        memory["hypotheses"] = deepcopy(
            interpretation[
                "hypotheses"
            ]
        )

        memory["continuity_note"] = (
            interpretation[
                "continuity_note"
            ]
        )

        self.snapshot[
            "interpreted_source_signature"
        ] = source_signature

        return deepcopy(
            self.snapshot
        )


class MutableSourceBuilder:
    def __init__(self):
        self.payload = _payload()
        self.signature = "source-v1"

    def __call__(
        self,
        candidate_id,
    ):
        return CareerMemorySourceSnapshot(
            candidate_id=candidate_id,
            payload=deepcopy(
                self.payload
            ),
            source_signature=(
                self.signature
            ),
        )


class FailingThenSuccessfulInterpreter:
    def __init__(self):
        self.calls = 0
        self.deltas = []

    def interpret(
        self,
        *,
        current_memory,
        recent_delta,
    ):
        self.calls += 1

        self.deltas.append(
            deepcopy(
                recent_delta
            )
        )

        if self.calls == 1:
            raise RuntimeError(
                "temporary LLM failure"
            )

        return {
            "inferences": [
                {
                    "statement": (
                        "Technical direction "
                        "may be strengthening."
                    ),
                    "confidence": 70,
                    "evidence_refs": [
                        (
                            "fact:"
                            "candidate_profile:"
                            "current"
                        )
                    ],
                }
            ],
            "hypotheses": [],
            "continuity_note": (
                "Watch technical-role evidence."
            ),
        }


class SuccessfulInterpreter:
    def __init__(self):
        self.calls = 0

    def interpret(
        self,
        *,
        current_memory,
        recent_delta,
    ):
        self.calls += 1

        return {
            "inferences": [],
            "hypotheses": [],
            "continuity_note": (
                "Interpreted."
            ),
        }


def test_failure_retry_success_same_memory_version():
    repository = FakeRepository()
    source = MutableSourceBuilder()

    interpreter = (
        FailingThenSuccessfulInterpreter()
    )

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
        interpreter=interpreter,
    )

    first = manager.refresh(
        "candidate-1"
    )

    # Deterministic memory succeeds even
    # though interpretation fails.
    assert first["changed"] is True
    assert (
        first["snapshot"][
            "memory_version"
        ]
        == 1
    )

    assert (
        first["interpretation_pending"]
        is True
    )

    assert (
        first["interpretation_attempted"]
        is True
    )

    assert (
        first["interpretation_applied"]
        is False
    )

    assert (
        "temporary LLM failure"
        in first[
            "interpretation_error"
        ]
    )

    assert (
        repository.snapshot[
            "interpreted_source_signature"
        ]
        == ""
    )

    # Source did not change. This is a retry,
    # not a new professional memory version.
    second = manager.refresh(
        "candidate-1"
    )

    assert second["changed"] is False

    assert (
        second["snapshot"][
            "memory_version"
        ]
        == 1
    )

    assert (
        second["interpretation_pending"]
        is False
    )

    assert (
        second["interpretation_attempted"]
        is True
    )

    assert (
        second["interpretation_applied"]
        is True
    )

    assert (
        second["interpretation_error"]
        is None
    )

    assert (
        second["snapshot"][
            "interpreted_source_signature"
        ]
        == "source-v1"
    )

    assert interpreter.calls == 2

    # First attempt uses precise fresh delta.
    assert (
        len(
            interpreter.deltas[0]
        )
        == 5
    )

    # Retry reconstructs complete current
    # authoritative state, also 5 sections.
    assert (
        len(
            interpreter.deltas[1]
        )
        == 5
    )

    # Once synchronized, another refresh is
    # a true zero-IA NO-OP.
    third = manager.refresh(
        "candidate-1"
    )

    assert third["changed"] is False

    assert (
        third["interpretation_pending"]
        is False
    )

    assert (
        third["interpretation_attempted"]
        is False
    )

    assert (
        third["interpretation_applied"]
        is False
    )

    assert interpreter.calls == 2
    assert repository.save_calls == 1
    assert repository.apply_calls == 1


def test_new_professional_source_creates_new_version_and_interprets_it():
    repository = FakeRepository()
    source = MutableSourceBuilder()

    interpreter = SuccessfulInterpreter()

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
        interpreter=interpreter,
    )

    first = manager.refresh(
        "candidate-1"
    )

    assert (
        first["snapshot"][
            "memory_version"
        ]
        == 1
    )

    assert (
        first["snapshot"][
            "interpreted_source_signature"
        ]
        == "source-v1"
    )

    source.payload[
        "market_evidence"
    ] = {
        "sample_size": 11,
    }

    source.signature = "source-v2"

    second = manager.refresh(
        "candidate-1"
    )

    assert second["changed"] is True

    assert (
        second["snapshot"][
            "memory_version"
        ]
        == 2
    )

    assert (
        len(
            second["recent_delta"]
        )
        == 1
    )

    assert (
        second["recent_delta"][0][
            "evidence_ref"
        ]
        == (
            "market_evidence:"
            "market_position:"
            "historical"
        )
    )

    assert (
        second["snapshot"][
            "interpreted_source_signature"
        ]
        == "source-v2"
    )

    assert interpreter.calls == 2


def test_no_interpreter_keeps_memory_pending_without_failure():
    repository = FakeRepository()
    source = MutableSourceBuilder()

    manager = CareerMemoryManager(
        repository=repository,
        source_builder=source,
        interpreter=None,
    )

    first = manager.refresh(
        "candidate-1"
    )

    assert first["changed"] is True

    assert (
        first["interpretation_pending"]
        is True
    )

    assert (
        first["interpretation_attempted"]
        is False
    )

    assert (
        first["interpretation_error"]
        is None
    )

    second = manager.refresh(
        "candidate-1"
    )

    assert second["changed"] is False

    assert (
        second["snapshot"][
            "memory_version"
        ]
        == 1
    )

    assert (
        second["interpretation_pending"]
        is True
    )
