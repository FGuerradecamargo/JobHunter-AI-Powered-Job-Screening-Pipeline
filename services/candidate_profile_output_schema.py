"""Provider-facing structured output contract for candidate profiles.

This schema guarantees transport/output shape only.
Source authority and evidence rules remain the responsibility of
structured_interpretation_validation.
"""
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)


class _StrictOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class CandidateCapabilityOutput(
    _StrictOutput
):
    capability_id: str
    label: str
    evidence_refs: list[str]
    contexts: list[str]
    outcomes: list[str]
    transferable: bool


class CandidateCheckpointOutput(
    _StrictOutput
):
    current_position: str
    proven_strengths: list[str]
    transferable_strengths: list[str]
    evidence_missing: list[str]
    confirmed_gaps: list[str]
    current_direction: list[str]
    open_questions: list[str]
    changes_since_previous_version: list[str]
    possible_next_profile_triggers: list[str]
    authority: Literal[
        "derived_checkpoint"
    ]


class CandidatePreferenceOutput(
    _StrictOutput
):
    kind: str
    value: str
    semantic: Literal[
        "preference",
        "allowed_set",
        "constraint",
    ]
    evidence_refs: list[str]


class CandidateLanguageOutput(
    _StrictOutput
):
    name: str
    proficiency: str
    evidence_refs: list[str]


class CandidateLicenceOutput(
    _StrictOutput
):
    name: str
    jurisdiction: str
    status: Literal[
        "active",
        "expired",
        "pending",
        "unknown",
    ]
    expiry: str
    evidence_refs: list[str]


class CandidateWorkAuthorizationOutput(
    _StrictOutput
):
    jurisdiction: str
    status: str
    evidence_refs: list[str]


class CandidateFactCoverageOutput(
    _StrictOutput
):
    languages: Literal[
        "confirmed_complete",
        "partial",
        "unknown",
    ]
    licences: Literal[
        "confirmed_complete",
        "partial",
        "unknown",
    ]
    work_authorizations: Literal[
        "confirmed_complete",
        "partial",
        "unknown",
    ]
    constraints: Literal[
        "confirmed_complete",
        "partial",
        "unknown",
    ]
    compensation: Literal[
        "confirmed_complete",
        "partial",
        "unknown",
    ]
    work_modes: Literal[
        "confirmed_complete",
        "partial",
        "unknown",
    ]
    employment_types: Literal[
        "confirmed_complete",
        "partial",
        "unknown",
    ]


class CandidateProfileOutput(
    _StrictOutput
):
    capabilities: list[
        CandidateCapabilityOutput
    ]
    checkpoint: CandidateCheckpointOutput
    contexts: list[str]
    evidence_summaries: list[str]
    confirmed_gaps: list[str]
    evidence_gaps: list[str]
    objectives: list[str]
    preferences: list[str]
    seniority: str
    responsibility_scope: str
    structured_preferences: list[
        CandidatePreferenceOutput
    ]
    languages: list[
        CandidateLanguageOutput
    ]
    licences: list[
        CandidateLicenceOutput
    ]
    work_authorizations: list[
        CandidateWorkAuthorizationOutput
    ]
    fact_coverage: (
        CandidateFactCoverageOutput
    )
