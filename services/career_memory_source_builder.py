from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any

from models.candidate import Candidate
from models.career_objective import CareerObjective
from models.career_update import CareerUpdate

from services.candidate_repository import (
    CandidateRepository,
)
from services.career_objective_repository import (
    CareerObjectiveRepository,
)
from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.database import (
    list_candidate_application_outcomes,
)
from services.market_position_service import (
    build_market_position,
)


@dataclass(frozen=True)
class CareerMemorySourceSnapshot:
    candidate_id: str
    payload: dict[str, Any]
    source_signature: str


_UNORDERED_CANDIDATE_LIST_FIELDS = {
    "target_roles",
    "spoken_languages",
    "skills",
    "strengths",
    "development_areas",
    "proven_capabilities",
    "transferable_capabilities",
    "developing_capabilities",
    "technical_tools",
    "domain_experience",
    "competitive_role_families",
    "bridge_role_families",
    "target_role_families",
}


_OUTCOME_FIELDS = (
    "job_id",
    "final_status",
    "interview_stage",
    "rejection_reason",
    "recruiter_feedback",
    "candidate_notes",
    "offer_salary",
    "offer_currency",
    "lessons_learned",
    "outcome_date",
)


def _normalize_string(
    value: Any,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    )


def _normalize_string_list(
    values: Any,
) -> list[str]:
    if not isinstance(
        values,
        (list, tuple, set),
    ):
        return []

    normalized = {
        _normalize_string(value)
        for value in values
        if _normalize_string(value)
    }

    return sorted(
        normalized,
        key=lambda value: value.casefold(),
    )


def _canonicalize(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(
                item
            )
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(
                    pair[0]
                ),
            )
        }

    if isinstance(value, list):
        return [
            _canonicalize(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            _canonicalize(item)
            for item in value
        ]

    if isinstance(value, str):
        return _normalize_string(
            value
        )

    return value


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_source_signature(
    payload: dict[str, Any],
) -> str:
    canonical = _canonical_json(
        payload
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _candidate_payload(
    candidate: Candidate,
) -> dict[str, Any]:
    data = asdict(
        candidate
    )

    # Candidate identity scopes the memory in DB.
    # Name is not career evidence and should not make
    # Career Memory stale after a cosmetic rename.
    data.pop("id", None)
    data.pop("name", None)

    for field_name in (
        _UNORDERED_CANDIDATE_LIST_FIELDS
    ):
        data[field_name] = (
            _normalize_string_list(
                data.get(
                    field_name,
                    [],
                )
            )
        )

    return _canonicalize(
        data
    )


def _objective_payload(
    objective: CareerObjective | None,
) -> dict[str, Any]:
    if objective is None:
        return {}

    return {
        "title": _normalize_string(
            objective.title
        ),
        "description": _normalize_string(
            objective.description
        ),
        "active": bool(
            objective.active
        ),
        "desired_role_families": (
            _normalize_string_list(
                objective.desired_role_families
            )
        ),
    }


def _career_updates_payload(
    career_updates: list[
        CareerUpdate
    ],
) -> list[dict[str, Any]]:
    updates = [
        {
            "id": _normalize_string(
                update.id
            ),
            "update_type": (
                _normalize_string(
                    update.update_type
                )
            ),
            "description": (
                _normalize_string(
                    update.description
                )
            ),
        }
        for update in career_updates
    ]

    return sorted(
        updates,
        key=lambda item: (
            item["id"],
            item["update_type"],
            item["description"],
        ),
    )


def _market_payload(
    market_position: dict[str, Any],
) -> dict[str, Any]:
    historical = (
        market_position.get(
            "historical",
            {},
        )
        if isinstance(
            market_position,
            dict,
        )
        else {}
    )

    return _canonicalize(
        historical
        if isinstance(
            historical,
            dict,
        )
        else {}
    )


def _outcomes_payload(
    outcomes: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    normalized = []

    for outcome in outcomes:
        if not isinstance(
            outcome,
            dict,
        ):
            continue

        item = {
            field: _canonicalize(
                outcome.get(
                    field,
                    "",
                )
            )
            for field in _OUTCOME_FIELDS
        }

        normalized.append(
            item
        )

    return sorted(
        normalized,
        key=lambda item: (
            str(
                item.get(
                    "job_id",
                    "",
                )
            ),
            str(
                item.get(
                    "outcome_date",
                    "",
                )
            ),
            str(
                item.get(
                    "final_status",
                    "",
                )
            ),
        ),
    )


def build_career_memory_source_payload(
    *,
    candidate: Candidate,
    objective: CareerObjective | None,
    career_updates: list[
        CareerUpdate
    ],
    market_position: dict[str, Any],
    application_outcomes: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    return {
        "candidate": (
            _candidate_payload(
                candidate
            )
        ),
        "career_objective": (
            _objective_payload(
                objective
            )
        ),
        "career_updates": (
            _career_updates_payload(
                career_updates
            )
        ),
        "market_evidence": (
            _market_payload(
                market_position
            )
        ),
        "application_outcomes": (
            _outcomes_payload(
                application_outcomes
            )
        ),
    }


def build_career_memory_source_snapshot(
    candidate_id: str,
) -> CareerMemorySourceSnapshot:
    normalized_candidate_id = (
        _normalize_string(
            candidate_id
        )
    )

    if not normalized_candidate_id:
        raise ValueError(
            "candidate_id must be non-empty."
        )

    candidate_repository = (
        CandidateRepository()
    )

    candidate = candidate_repository.get(
        normalized_candidate_id
    )

    if candidate is None:
        raise ValueError(
            "Candidate was not found: "
            f"{normalized_candidate_id}"
        )

    objective_repository = (
        CareerObjectiveRepository()
    )

    update_repository = (
        CareerUpdateRepository()
    )

    objective = (
        objective_repository.get_active(
            normalized_candidate_id
        )
    )

    career_updates = (
        update_repository.list_for_candidate(
            normalized_candidate_id
        )
    )

    market_position = (
        build_market_position(
            candidate_id=(
                normalized_candidate_id
            ),
            batch_signals=[],
        )
    )

    outcomes = (
        list_candidate_application_outcomes(
            normalized_candidate_id
        )
    )

    payload = (
        build_career_memory_source_payload(
            candidate=candidate,
            objective=objective,
            career_updates=career_updates,
            market_position=market_position,
            application_outcomes=outcomes,
        )
    )

    return CareerMemorySourceSnapshot(
        candidate_id=normalized_candidate_id,
        payload=payload,
        source_signature=(
            build_source_signature(
                payload
            )
        ),
    )
