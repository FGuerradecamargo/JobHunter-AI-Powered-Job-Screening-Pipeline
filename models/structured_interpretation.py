"""Provider-neutral, private in-memory contracts. Diagnostics are a separate projection."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from models.hiring_case import OpportunitySignalKind, OpportunitySignalState, RequirementEvidenceState, RequirementImportance
from models.hiring_case import TemporalApplicability
from models.profile_interpretation import (
    AIJobProfileSnapshot, CandidateProfileDraft, CandidateProfileSnapshot,
    InterpretationAuthority, JobHardFacts, JobProfileDraft, ProfileCheckpoint,
)


class InterpretationOperation(str, Enum):
    BUILD_CANDIDATE_PROFILE = "build_candidate_profile"
    BUILD_JOB_PROFILE = "build_job_profile"
    ANALYZE_HIRING_CASE = "analyze_hiring_case"
    INTERPRET_OPPORTUNITY_VALUE = "interpret_opportunity_value"


class ValidationStatus(str, Enum):
    ACCEPTED = "accepted"
    NORMALIZED = "normalized"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class ValidationIssue(str, Enum):
    UNSUPPORTED_TEMPORAL_REQUIREMENT = "unsupported_temporal_requirement"
    INVALID_TEMPORAL_METADATA = "invalid_temporal_metadata"
    UNSUPPORTED_DIRECT_EVIDENCE_REQUIREMENT = "unsupported_direct_evidence_requirement"
    CONFLICTING_PREFERENCES = "conflicting_preferences"
    INVALID_SCHEMA = "invalid_schema"
    INVALID_SCOPE = "invalid_scope"
    UNKNOWN_REF = "unknown_ref"
    CHECKPOINT_AS_EVIDENCE = "checkpoint_as_evidence"
    WRONG_SOURCE_CLASS = "wrong_source_class"
    MISSING_EVIDENCE = "missing_evidence"
    UNCONFIRMED_GAP = "unconfirmed_gap"
    UNSUPPORTED_BLOCKER = "unsupported_blocker"
    UNKNOWN_OPPORTUNITY_FACT = "unknown_opportunity_fact"
    UNSUPPORTED_OPPORTUNITY = "unsupported_opportunity"
    UNKNOWN_CAPABILITY = "unknown_capability"
    TRANSFERABLE_PROMOTION = "transferable_promotion"
    UNKNOWN_NEED = "unknown_need"
    STALE_INPUT = "stale_input"
    FIXTURE_UNAVAILABLE = "fixture_unavailable"


class SourceRefClass(str, Enum):
    CANDIDATE_EVIDENCE = "candidate_evidence"
    CAREER_MEMORY_SOURCE = "career_memory_source"
    JOB_HARD_FACT = "job_hard_fact"
    DERIVED_CHECKPOINT = "derived_checkpoint"
    UNKNOWN = "unknown"


class FactState(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class LinkConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class LinkReason(str, Enum):
    SOURCE_REFERENCE_UNAVAILABLE = "source_reference_unavailable"
    DIRECT_SUPPORT = "direct_support"
    ADJACENT_SUPPORT = "adjacent_support"
    NEEDS_EXAMPLE = "needs_example"
    CONFIRMED_ABSENCE = "confirmed_absence"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class RegisteredSourceRef:
    ref: str
    source_class: SourceRefClass
    owner_id: str
    source_type: str
    usable_evidence: bool = False
    confirmed_absence_for: tuple[str, ...] = ()
    temporal_need_id: str = ""
    temporal_version: str = ""
    performed_on: str = ""


@dataclass(frozen=True)
class OpportunityFact:
    kind: OpportunitySignalKind
    state: FactState
    supporting_refs: tuple[str, ...] = ()
    # Only explicit, known source facts; never an interpreter output.
    facts: tuple[str, ...] = ()
    # Trusted unresolved conflict: sources are current and equally authoritative.
    conflicting_preference_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticLink:
    need_id: str
    candidate_capability_id: str | None
    assessment: RequirementEvidenceState
    evidence_refs: tuple[str, ...]
    confidence: LinkConfidence
    reason_code: LinkReason
    needs_evidence: bool
    uncertainty: str = ""
    evidence_question_hint: str = ""
    needs_source_repair: bool = False
    temporal_applicability: TemporalApplicability = TemporalApplicability.NOT_APPLICABLE


@dataclass(frozen=True)
class SemanticLinks:
    links: tuple[SemanticLink, ...]


@dataclass(frozen=True)
class InterpretedOpportunitySignal:
    kind: OpportunitySignalKind
    factual_state: FactState
    state: OpportunitySignalState
    authority: InterpretationAuthority
    supporting_refs: tuple[str, ...]
    importance: RequirementImportance
    uncertainty: str = ""


@dataclass(frozen=True)
class OpportunityInterpretation:
    signals: tuple[InterpretedOpportunitySignal, ...]


@dataclass(frozen=True)
class StructuredInterpretationInput:
    operation: InterpretationOperation
    candidate_id: str = ""
    job_id: str = ""
    memory_signature: str = ""
    memory_projection: dict | None = None
    source_registry: tuple[RegisteredSourceRef, ...] = ()
    previous_checkpoint: ProfileCheckpoint | None = None
    candidate_profile: CandidateProfileSnapshot | None = None
    job_profile: AIJobProfileSnapshot | None = None
    hard_facts: JobHardFacts | None = None
    opportunity_facts: tuple[OpportunityFact, ...] = ()
    seniority_context_mismatch: bool = False
    schema_version: str = "structured-interpretation-input-v1"
    # Trusted source-layer detection of an existing record with broken provenance.
    source_repair_need_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterpretationResult:
    operation: InterpretationOperation
    input_signature: str
    output_payload: CandidateProfileDraft | JobProfileDraft | SemanticLinks | OpportunityInterpretation | None
    produced_at: str
    validation_status: ValidationStatus
    validation_issue_codes: tuple[ValidationIssue, ...] = ()
    schema_version: str = "structured-interpretation-result-v1"
    interpreter_version: str = "fixture-structured-interpreter-v1"
    authoritative: bool = False


class StructuredInterpreter(Protocol):
    def interpret(self, request: StructuredInterpretationInput) -> InterpretationResult: ...
