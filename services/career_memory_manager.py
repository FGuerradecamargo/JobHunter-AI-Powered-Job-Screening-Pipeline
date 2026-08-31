from __future__ import annotations

from typing import Any, Callable

from services.career_memory_repository import (
    CareerMemoryRepository,
)
from services.career_memory_source_builder import (
    CareerMemorySourceSnapshot,
    build_career_memory_source_snapshot,
)


CAREER_MEMORY_SCHEMA_VERSION = (
    "career-memory-v1"
)


_SECTION_EVENT_CONFIG = {
    "candidate": {
        "event_type": (
            "candidate_profile_state"
        ),
        "authority": "fact",
        "source_type": (
            "candidate_profile"
        ),
        "source_ref": "current",
    },
    "career_objective": {
        "event_type": (
            "career_objective_state"
        ),
        "authority": "fact",
        "source_type": (
            "career_objective"
        ),
        "source_ref": "active",
    },
    "career_updates": {
        "event_type": (
            "career_updates_state"
        ),
        "authority": "fact",
        "source_type": (
            "career_updates"
        ),
        "source_ref": "collection",
    },
    "market_evidence": {
        "event_type": (
            "market_evidence_state"
        ),
        "authority": (
            "market_evidence"
        ),
        "source_type": (
            "market_position"
        ),
        "source_ref": "historical",
    },
    "application_outcomes": {
        "event_type": (
            "application_outcomes_state"
        ),
        "authority": "outcome",
        "source_type": (
            "application_outcomes"
        ),
        "source_ref": "collection",
    },
}


def _safe_list(
    value: Any,
) -> list[Any]:
    if not isinstance(
        value,
        list,
    ):
        return []

    return value


def _safe_string(
    value: Any,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        return ""

    return value


def _section_default(
    section: str,
) -> Any:
    if section in {
        "career_updates",
        "application_outcomes",
    }:
        return []

    return {}


def _previous_section_state(
    *,
    memory: dict[str, Any],
    section: str,
) -> Any:
    if not isinstance(
        memory,
        dict,
    ):
        return _section_default(
            section
        )

    if section == "candidate":
        facts = memory.get(
            "facts",
            {},
        )

        if not isinstance(
            facts,
            dict,
        ):
            return {}

        return facts.get(
            "candidate",
            {},
        )

    if section == "career_objective":
        facts = memory.get(
            "facts",
            {},
        )

        if not isinstance(
            facts,
            dict,
        ):
            return {}

        return facts.get(
            "career_objective",
            {},
        )

    if section == "career_updates":
        facts = memory.get(
            "facts",
            {},
        )

        if not isinstance(
            facts,
            dict,
        ):
            return []

        value = facts.get(
            "career_updates",
            [],
        )

        return (
            value
            if isinstance(value, list)
            else []
        )

    if section == "market_evidence":
        value = memory.get(
            "market_evidence",
            {},
        )

        return (
            value
            if isinstance(value, dict)
            else {}
        )

    if section == "application_outcomes":
        value = memory.get(
            "outcomes",
            [],
        )

        return (
            value
            if isinstance(value, list)
            else []
        )

    raise ValueError(
        "Unknown Career Memory section: "
        f"{section}"
    )


def _build_recent_delta(
    *,
    source_payload: dict[str, Any],
    previous_memory: dict[str, Any],
    force_full_delta: bool,
) -> list[dict[str, Any]]:
    delta: list[
        dict[str, Any]
    ] = []

    for (
        section,
        config,
    ) in _SECTION_EVENT_CONFIG.items():
        current_state = (
            source_payload.get(
                section,
                _section_default(
                    section
                ),
            )
        )

        previous_state = (
            _previous_section_state(
                memory=previous_memory,
                section=section,
            )
        )

        if (
            not force_full_delta
            and current_state
            == previous_state
        ):
            continue

        authority = str(
            config["authority"]
        )

        source_type = str(
            config["source_type"]
        )

        source_ref = str(
            config["source_ref"]
        )

        delta.append(
            {
                "evidence_ref": (
                    f"{authority}:"
                    f"{source_type}:"
                    f"{source_ref}"
                ),
                "event_type": str(
                    config[
                        "event_type"
                    ]
                ),
                "authority": authority,
                "source_type": source_type,
                "source_ref": source_ref,
                "state": current_state,
            }
        )

    return delta


def _build_memory(
    *,
    source_payload: dict[str, Any],
    previous_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    previous = (
        previous_memory
        if isinstance(
            previous_memory,
            dict,
        )
        else {}
    )

    return {
        "facts": {
            "candidate": (
                source_payload.get(
                    "candidate",
                    {},
                )
            ),
            "career_objective": (
                source_payload.get(
                    "career_objective",
                    {},
                )
            ),
            "career_updates": (
                source_payload.get(
                    "career_updates",
                    [],
                )
            ),
        },

        "market_evidence": (
            source_payload.get(
                "market_evidence",
                {},
            )
        ),

        "outcomes": (
            source_payload.get(
                "application_outcomes",
                [],
            )
        ),

        # These are deliberately preserved rather
        # than regenerated from authoritative facts.
        #
        # Later AI compaction may update them, but
        # deterministic source refresh must never
        # promote or invent them.
        "inferences": _safe_list(
            previous.get(
                "inferences",
                [],
            )
        ),

        "hypotheses": _safe_list(
            previous.get(
                "hypotheses",
                [],
            )
        ),

        "continuity_note": _safe_string(
            previous.get(
                "continuity_note",
                "",
            )
        ),
    }


class CareerMemoryManager:
    def __init__(
        self,
        repository: CareerMemoryRepository | None = None,
        source_builder: Callable[
            [str],
            CareerMemorySourceSnapshot,
        ] = build_career_memory_source_snapshot,
    ) -> None:
        self.repository = (
            repository
            or CareerMemoryRepository()
        )

        self.source_builder = (
            source_builder
        )

    def refresh(
        self,
        candidate_id: str,
    ) -> dict[str, Any]:
        normalized_candidate_id = str(
            candidate_id or ""
        ).strip()

        if not normalized_candidate_id:
            raise ValueError(
                "candidate_id must be non-empty."
            )

        source = self.source_builder(
            normalized_candidate_id
        )

        existing = (
            self.repository.get_snapshot(
                normalized_candidate_id
            )
        )

        if (
            existing
            and existing.get(
                "source_signature"
            )
            == source.source_signature
            and existing.get(
                "memory_schema_version"
            )
            == CAREER_MEMORY_SCHEMA_VERSION
        ):
            return {
                "changed": False,
                "new_events": 0,
                "recent_delta": [],
                "snapshot": existing,
                "source_signature": (
                    source.source_signature
                ),
            }

        previous_memory = (
            existing.get(
                "memory",
                {},
            )
            if existing
            else {}
        )

        previous_schema_version = (
            existing.get(
                "memory_schema_version"
            )
            if existing
            else None
        )

        recent_delta = (
            _build_recent_delta(
                source_payload=(
                    source.payload
                ),
                previous_memory=(
                    previous_memory
                ),
                force_full_delta=(
                    existing is None
                    or previous_schema_version
                    != CAREER_MEMORY_SCHEMA_VERSION
                ),
            )
        )

        new_events = 0

        for item in recent_delta:
            inserted = (
                self.repository.append_event(
                    candidate_id=(
                        normalized_candidate_id
                    ),
                    event_type=(
                        item[
                            "event_type"
                        ]
                    ),
                    authority=(
                        item[
                            "authority"
                        ]
                    ),
                    source_type=(
                        item[
                            "source_type"
                        ]
                    ),
                    source_ref=(
                        item[
                            "source_ref"
                        ]
                    ),
                    payload={
                        "state": (
                            item[
                                "state"
                            ]
                        ),
                    },
                )
            )

            if inserted:
                new_events += 1

        memory = _build_memory(
            source_payload=(
                source.payload
            ),
            previous_memory=(
                previous_memory
            ),
        )

        snapshot = (
            self.repository.save_snapshot(
                candidate_id=(
                    normalized_candidate_id
                ),
                memory=memory,
                source_signature=(
                    source.source_signature
                ),
                memory_schema_version=(
                    CAREER_MEMORY_SCHEMA_VERSION
                ),
            )
        )

        return {
            "changed": True,
            "new_events": new_events,
            "recent_delta": recent_delta,
            "snapshot": snapshot,
            "source_signature": (
                source.source_signature
            ),
        }


def refresh_career_memory(
    candidate_id: str,
) -> dict[str, Any]:
    return CareerMemoryManager().refresh(
        candidate_id
    )
