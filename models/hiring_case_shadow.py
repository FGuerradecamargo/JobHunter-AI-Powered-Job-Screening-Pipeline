"""Inputs are private; comparison outputs contain only enums and counts."""

from dataclasses import dataclass, field
from enum import Enum

from models.application_contract import ApplicationAnalysisSource
from models.candidate import Candidate
from models.career_objective import CareerObjective
from models.career_update import CareerUpdate
from models.hiring_case import (
    HIRING_CASE_SCHEMA_VERSION,
    HiringCaseClassification,
    HiringCaseStrength,
    OpportunityConfidence,
    OpportunityValue,
)
from models.job_profile import JobProfile


class LegacyHiringClassification(str, Enum):
    BEST_MATCH = "best_match"
    POTENTIAL = "potential"
    GOOD_OPPORTUNITY = "good_opportunity"
    COMPETITIVE = "competitive"
    REJECT = "reject"
    UNKNOWN = "unknown"


class ShadowComparisonState(str, Enum):
    SAME = "same"
    DIFFERENT = "different"
    UNMAPPED = "unmapped"
    NOT_EVALUATED = "not_evaluated"


class ShadowUnavailableReason(str, Enum):
    ANALYSIS_MISSING = "analysis_missing"
    CORE_REQUIREMENTS_MISSING = "core_requirements_missing"


@dataclass(frozen=True)
class ConfirmedCapabilityGap:
    """Explicit reviewer confirmation, not inferred from an LLM gap or silence.

    The caller must have verified that the referenced existing career update
    confirms insufficient capability for this requirement. No text is interpreted
    or persisted here. This is a trusted local input, not a user-facing endpoint.
    """

    candidate_id: str
    job_id: str
    requirement: str
    source_update_id: str


@dataclass(frozen=True)
class HiringCaseShadowSource:
    candidate: Candidate
    analysis_source: ApplicationAnalysisSource
    job_profile: JobProfile | None = None
    objective: CareerObjective | None = None
    career_updates: tuple[CareerUpdate, ...] = ()
    confirmed_gaps: tuple[ConfirmedCapabilityGap, ...] = ()


@dataclass(frozen=True)
class HiringCaseShadowComparison:
    legacy_value: LegacyHiringClassification
    shadow_classification: HiringCaseClassification | None
    comparison: ShadowComparisonState
    hiring_case_strength: HiringCaseStrength | None
    opportunity_value: OpportunityValue | None
    opportunity_confidence: OpportunityConfidence | None
    proven_count: int = 0
    transferable_count: int = 0
    evidence_missing_count: int = 0
    gap_count: int = 0
    core_gap_count: int = 0
    needs_evidence_count: int = 0
    unavailable_reason: ShadowUnavailableReason | None = None
    schema_version: str = field(default=HIRING_CASE_SCHEMA_VERSION, init=False)
    comparison_schema_version: str = field(default="hiring-case-shadow-v1", init=False)
    adapter_version: str = field(default="hiring-case-input-adapter-v1", init=False)
    authoritative: bool = field(default=False, init=False)
