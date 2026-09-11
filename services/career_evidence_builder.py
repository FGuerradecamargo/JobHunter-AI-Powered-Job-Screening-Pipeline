from __future__ import annotations

import hashlib
import re
from typing import Any

from models.candidate import Candidate
from models.career_evidence import CareerEvidence
from models.career_update import CareerUpdate
from services.role_family_normalizer import normalize_role_family


_CANDIDATE_SIGNAL_FIELDS = {
    "skills": "skill",
    "strengths": "strength",
    "proven_capabilities": "proven_capability",
    "transferable_capabilities": "transferable_capability",
    "developing_capabilities": "developing_capability",
    "technical_tools": "technical_tool",
    "domain_experience": "domain_experience",
}


def _normalize(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    )


def _evidence_id(
    *,
    evidence_type: str,
    signal_type: str,
    source_ref: str,
    statement: str,
    role_family: str = "",
) -> str:
    canonical = "|".join(
        [
            _normalize(evidence_type).casefold(),
            _normalize(signal_type).casefold(),
            _normalize(source_ref).casefold(),
            _normalize(statement).casefold(),
            _normalize(role_family).casefold(),
        ]
    )

    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    return f"evidence_{digest}"


def _record(
    *,
    evidence_type: str,
    signal_type: str,
    source_ref: str,
    statement: str,
    role_family: str = "",
    observed_at: str = "",
    authority: str,
    metadata: dict[str, Any] | None = None,
) -> CareerEvidence | None:
    normalized_statement = _normalize(
        statement
    )

    if not normalized_statement:
        return None

    normalized_role_family = _normalize(
        role_family
    )

    return CareerEvidence(
        evidence_id=_evidence_id(
            evidence_type=evidence_type,
            signal_type=signal_type,
            source_ref=source_ref,
            statement=normalized_statement,
            role_family=normalized_role_family,
        ),
        evidence_type=_normalize(
            evidence_type
        ),
        signal_type=_normalize(
            signal_type
        ),
        source_ref=_normalize(
            source_ref
        ),
        statement=normalized_statement,
        role_family=normalized_role_family,
        observed_at=_normalize(
            observed_at
        ),
        authority=_normalize(
            authority
        ),
        metadata=dict(
            metadata or {}
        ),
    )


def build_candidate_evidence(
    candidate: Candidate,
) -> list[CareerEvidence]:
    evidence: list[CareerEvidence] = []

    for (
        field_name,
        signal_type,
    ) in _CANDIDATE_SIGNAL_FIELDS.items():
        values = getattr(
            candidate,
            field_name,
            [],
        )

        for value in values or []:
            normalized = _normalize(
                value
            )

            record = _record(
                evidence_type="candidate_fact",
                signal_type=signal_type,
                source_ref=(
                    f"candidate:{field_name}:"
                    f"{normalized.casefold()}"
                ),
                statement=normalized,
                authority="fact",
            )

            if record is not None:
                evidence.append(record)

    return evidence


def build_career_update_evidence(
    updates: list[CareerUpdate],
) -> list[CareerEvidence]:
    evidence: list[CareerEvidence] = []

    for update in updates or []:
        record = _record(
            evidence_type="career_update",
            signal_type=(
                update.update_type
                or "career_update"
            ),
            source_ref=(
                f"career_update:{update.id}"
            ),
            statement=update.description,
            observed_at=update.created_at,
            authority="fact",
        )

        if record is not None:
            evidence.append(record)

    return evidence


def build_market_evidence(
    signals: list[dict[str, Any]],
) -> list[CareerEvidence]:
    evidence: list[CareerEvidence] = []

    for item in signals or []:
        if not isinstance(
            item,
            dict,
        ):
            continue

        job_id = _normalize(
            item.get("job_id")
        )

        if not job_id:
            continue

        market_signal = (
            item.get("market_signal")
            or {}
        )

        if not isinstance(
            market_signal,
            dict,
        ):
            continue

        role_family = normalize_role_family(
            market_signal.get(
                "role_family"
            )
        )

        metadata = {
            "job_id": job_id,
            "recommendation": item.get(
                "recommendation"
            ),
            "current_fit": item.get(
                "current_fit"
            ),
        }

        if role_family:
            record = _record(
                evidence_type="market_signal",
                signal_type="role_family",
                source_ref=f"job:{job_id}",
                statement=role_family,
                role_family=role_family,
                authority="market_evidence",
                metadata=metadata,
            )

            if record is not None:
                evidence.append(record)

        for (
            source_field,
            signal_type,
        ) in (
            (
                "market_strengths",
                "market_strength",
            ),
            (
                "best_match_blockers",
                "best_match_blocker",
            ),
            (
                "what_would_raise_fit",
                "raise_fit",
            ),
        ):
            values = market_signal.get(
                source_field,
                [],
            )

            if not isinstance(
                values,
                list,
            ):
                continue

            for value in values:
                record = _record(
                    evidence_type=(
                        "market_signal"
                    ),
                    signal_type=signal_type,
                    source_ref=(
                        f"job:{job_id}"
                    ),
                    statement=value,
                    role_family=role_family,
                    authority=(
                        "market_evidence"
                    ),
                    metadata=metadata,
                )

                if record is not None:
                    evidence.append(
                        record
                    )

    return evidence


def build_outcome_evidence(
    outcomes: list[dict[str, Any]],
) -> list[CareerEvidence]:
    evidence: list[CareerEvidence] = []

    for outcome in outcomes or []:
        if not isinstance(
            outcome,
            dict,
        ):
            continue

        job_id = _normalize(
            outcome.get("job_id")
        )

        final_status = _normalize(
            outcome.get("final_status")
        )

        if not job_id or not final_status:
            continue

        observed_at = _normalize(
            outcome.get("outcome_date")
        )

        record = _record(
            evidence_type=(
                "application_outcome"
            ),
            signal_type="final_status",
            source_ref=(
                f"application_outcome:"
                f"{job_id}:"
                f"{observed_at}:"
                f"{final_status.casefold()}"
            ),
            statement=final_status,
            observed_at=observed_at,
            authority="outcome",
            metadata={
                "job_id": job_id,
                "interview_stage": (
                    outcome.get(
                        "interview_stage"
                    )
                ),
                "rejection_reason": (
                    outcome.get(
                        "rejection_reason"
                    )
                ),
                "recruiter_feedback": (
                    outcome.get(
                        "recruiter_feedback"
                    )
                ),
                "candidate_notes": (
                    outcome.get(
                        "candidate_notes"
                    )
                ),
                "lessons_learned": (
                    outcome.get(
                        "lessons_learned"
                    )
                ),
                "offer_salary": (
                    outcome.get(
                        "offer_salary"
                    )
                ),
                "offer_currency": (
                    outcome.get(
                        "offer_currency"
                    )
                ),
            },
        )

        if record is not None:
            evidence.append(record)

    return evidence


def build_career_evidence_records(
    *,
    candidate: Candidate,
    career_updates: list[
        CareerUpdate
    ] | None = None,
    market_signals: list[
        dict[str, Any]
    ] | None = None,
    application_outcomes: list[
        dict[str, Any]
    ] | None = None,
) -> list[CareerEvidence]:
    records = [
        *build_candidate_evidence(
            candidate
        ),
        *build_career_update_evidence(
            career_updates or []
        ),
        *build_market_evidence(
            market_signals or []
        ),
        *build_outcome_evidence(
            application_outcomes or []
        ),
    ]

    unique: dict[
        str,
        CareerEvidence,
    ] = {}

    for record in records:
        unique[
            record.evidence_id
        ] = record

    return sorted(
        unique.values(),
        key=lambda item: (
            item.evidence_type,
            item.signal_type,
            item.source_ref,
            item.statement.casefold(),
        ),
    )
