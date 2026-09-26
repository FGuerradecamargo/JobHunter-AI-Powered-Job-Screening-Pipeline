from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from models.hiring_case import (
    EvidenceRequirement,
    TemporalRequirement,
    OpportunitySignal,
    RequirementEvidenceState,
    RequirementImportance,
)


CANDIDATE_PROFILE_SCHEMA_VERSION = "candidate-profile-v1"
AI_JOB_PROFILE_SCHEMA_VERSION = "ai-job-profile-v1"
JOB_HARD_FACTS_SCHEMA_VERSION = "job-hard-facts-v1"


class InterpretationAuthority(str, Enum):
    EXPLICIT = "explicit"
    STRONGLY_IMPLIED = "strongly_implied"
    UNKNOWN = "unknown"


class CoverageState(str, Enum):
    """How complete the source layer is for a finite candidate fact family."""

    CONFIRMED_COMPLETE = "confirmed_complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CandidatePreferenceSemantic(str, Enum):
    """Preference and constraint semantics must never be conflated."""

    PREFERENCE = "preference"
    ALLOWED_SET = "allowed_set"
    CONSTRAINT = "constraint"


class CredentialStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"
    UNKNOWN = "unknown"


class JobRequirementStatus(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    USEFUL = "useful"
    EXPLICITLY_NOT_REQUIRED = "explicitly_not_required"
    UNKNOWN = "unknown"


class RequirementSubstitutability(str, Enum):
    NON_SUBSTITUTABLE = "non_substitutable"
    SUBSTITUTABLE = "substitutable"
    UNKNOWN = "unknown"


class RequirementRelevance(str, Enum):
    CORE = "core"
    SUPPORTING = "supporting"
    MINOR = "minor"


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())


def _refs(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted({_clean(value) for value in values if _clean(value)}))


@dataclass(frozen=True)
class SourceEvidence:
    ref: str
    source_type: str
    summary: str
    authority: str = "source_fact"

    def __post_init__(self) -> None:
        if self.authority != "source_fact":
            raise ValueError("Candidate profile evidence must have source_fact authority.")
        if not _clean(self.ref) or not _clean(self.source_type):
            raise ValueError("Source evidence identity and type are required.")


@dataclass(frozen=True)
class CandidateFactCoverage:
    """
    Completeness metadata for finite candidate facts.

    A missing item may only be treated as confirmed absence when the
    corresponding family is CONFIRMED_COMPLETE. This encodes the V1 rule:
    not found != absent.
    """

    languages: CoverageState = CoverageState.UNKNOWN
    licences: CoverageState = CoverageState.UNKNOWN
    work_authorizations: CoverageState = CoverageState.UNKNOWN
    constraints: CoverageState = CoverageState.UNKNOWN
    compensation: CoverageState = CoverageState.UNKNOWN
    work_modes: CoverageState = CoverageState.UNKNOWN
    employment_types: CoverageState = CoverageState.UNKNOWN

    def confirms_absence(self, dimension: str) -> bool:
        if dimension not in {
            "languages",
            "licences",
            "work_authorizations",
            "constraints",
            "compensation",
            "work_modes",
            "employment_types",
        }:
            raise ValueError(f"Unknown candidate fact dimension: {dimension}")
        return getattr(self, dimension) is CoverageState.CONFIRMED_COMPLETE


@dataclass(frozen=True)
class CandidateLanguage:
    name: str
    proficiency: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean(self.name))
        object.__setattr__(self, "proficiency", _clean(self.proficiency))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        if not self.name:
            raise ValueError("Language name is required.")
        if not self.evidence_refs:
            raise ValueError("Candidate language requires source evidence refs.")


@dataclass(frozen=True)
class CandidateLicence:
    name: str
    jurisdiction: str = ""
    status: CredentialStatus = CredentialStatus.UNKNOWN
    expiry: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean(self.name))
        object.__setattr__(self, "jurisdiction", _clean(self.jurisdiction))
        object.__setattr__(self, "expiry", _clean(self.expiry))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        if not isinstance(self.status, CredentialStatus):
            raise ValueError("Invalid credential status.")
        if not self.name:
            raise ValueError("Licence/certification name is required.")
        if not self.evidence_refs:
            raise ValueError("Candidate licence requires source evidence refs.")


@dataclass(frozen=True)
class CandidateWorkAuthorization:
    jurisdiction: str
    status: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "jurisdiction", _clean(self.jurisdiction))
        object.__setattr__(self, "status", _clean(self.status))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        if not self.jurisdiction:
            raise ValueError("Work-authorization jurisdiction is required.")
        if not self.evidence_refs:
            raise ValueError("Work authorization requires source evidence refs.")


@dataclass(frozen=True)
class CandidatePreference:
    kind: str
    value: str
    semantic: CandidatePreferenceSemantic
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _clean(self.kind))
        object.__setattr__(self, "value", _clean(self.value))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        if not isinstance(self.semantic, CandidatePreferenceSemantic):
            raise ValueError("Invalid candidate preference semantic.")
        if not self.kind or not self.value:
            raise ValueError("Candidate preference kind and value are required.")
        if not self.evidence_refs:
            raise ValueError("Candidate preference requires source evidence refs.")


@dataclass(frozen=True)
class ProfileCapability:
    capability_id: str
    label: str
    evidence_refs: tuple[str, ...]
    contexts: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()
    transferable: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        if not _clean(self.capability_id) or not _clean(self.label):
            raise ValueError("Capability identity and label are required.")
        if not self.evidence_refs:
            raise ValueError("A profile capability requires source evidence refs.")


@dataclass(frozen=True)
class ProfileCheckpoint:
    current_position: str
    proven_strengths: tuple[str, ...] = ()
    transferable_strengths: tuple[str, ...] = ()
    evidence_missing: tuple[str, ...] = ()
    confirmed_gaps: tuple[str, ...] = ()
    current_direction: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    changes_since_previous_version: tuple[str, ...] = ()
    possible_next_profile_triggers: tuple[str, ...] = ()
    authority: str = "derived_checkpoint"

    def __post_init__(self) -> None:
        if self.authority != "derived_checkpoint":
            raise ValueError("A profile checkpoint is derived interpretation only.")


@dataclass(frozen=True)
class CandidateProfileSnapshot:
    candidate_id: str
    profile_version: int
    memory_signature: str
    created_at: str
    source_refs: tuple[str, ...]
    capabilities: tuple[ProfileCapability, ...]
    checkpoint: ProfileCheckpoint
    contexts: tuple[str, ...] = ()
    evidence_summaries: tuple[str, ...] = ()
    confirmed_gaps: tuple[str, ...] = ()
    evidence_gaps: tuple[str, ...] = ()
    objectives: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    seniority: str = ""
    responsibility_scope: str = ""
    structured_preferences: tuple[CandidatePreference, ...] = ()
    languages: tuple[CandidateLanguage, ...] = ()
    licences: tuple[CandidateLicence, ...] = ()
    work_authorizations: tuple[CandidateWorkAuthorization, ...] = ()
    fact_coverage: CandidateFactCoverage = field(default_factory=CandidateFactCoverage)
    supersedes_version: int | None = None
    schema_version: str = CANDIDATE_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", _refs(self.source_refs))
        if not _clean(self.candidate_id) or self.profile_version < 1:
            raise ValueError("Candidate profile identity and positive version are required.")
        if not _clean(self.memory_signature) or not _clean(self.created_at):
            raise ValueError("Candidate profile signature and timestamp are required.")
        available = set(self.source_refs)
        for capability in self.capabilities:
            if not set(capability.evidence_refs).issubset(available):
                raise ValueError("Capability evidence refs must exist in the source snapshot.")
        for item in (
            *self.structured_preferences,
            *self.languages,
            *self.licences,
            *self.work_authorizations,
        ):
            if not set(item.evidence_refs).issubset(available):
                raise ValueError("Structured candidate facts must cite the source snapshot.")

    def can_confirm_absence(self, dimension: str) -> bool:
        return self.fact_coverage.confirms_absence(dimension)


@dataclass(frozen=True)
class HardJobFact:
    fact_id: str
    kind: str
    value: str
    source_ref: str
    explicit: bool = True
    hard_blocker: bool = False
    evidence_requirement: EvidenceRequirement = EvidenceRequirement.DEFENSIBLE
    constraint_need_id: str = ""
    temporal_requirement: TemporalRequirement = TemporalRequirement.NOT_REQUIRED
    temporal_need_id: str = ""
    required_version: str = ""
    superseded_versions: tuple[str, ...] = ()
    material_change_on: str = ""
    requirement_status: JobRequirementStatus = JobRequirementStatus.UNKNOWN
    substitutability: RequirementSubstitutability = RequirementSubstitutability.UNKNOWN

    def __post_init__(self) -> None:
        if not self.explicit:
            raise ValueError("The hard job layer accepts explicit facts only.")
        if not isinstance(self.temporal_requirement, TemporalRequirement):
            raise ValueError("Invalid temporal requirement.")
        if self.temporal_requirement is TemporalRequirement.CURRENT_REQUIRED and not _clean(self.temporal_need_id):
            raise ValueError("Temporal constraints must identify their requirement.")
        if not isinstance(self.evidence_requirement, EvidenceRequirement):
            raise ValueError("Invalid evidence requirement.")
        if self.evidence_requirement is EvidenceRequirement.DIRECT_REQUIRED and not _clean(self.constraint_need_id):
            raise ValueError("Direct evidence constraints must identify their requirement.")
        if not isinstance(self.requirement_status, JobRequirementStatus):
            raise ValueError("Invalid requirement status.")
        if not isinstance(self.substitutability, RequirementSubstitutability):
            raise ValueError("Invalid requirement substitutability.")
        if not all(_clean(item) for item in (self.fact_id, self.kind, self.value, self.source_ref)):
            raise ValueError("Hard job facts require identity, value and provenance.")


@dataclass(frozen=True)
class JobHardFacts:
    job_id: str
    job_signature: str
    facts: tuple[HardJobFact, ...]
    schema_version: str = JOB_HARD_FACTS_SCHEMA_VERSION

    @property
    def fact_refs(self) -> tuple[str, ...]:
        return tuple(sorted({item.fact_id for item in self.facts}))


@dataclass(frozen=True)
class InterpretedJobNeed:
    need_id: str
    label: str
    importance: RequirementImportance
    authority: InterpretationAuthority
    hard_fact_refs: tuple[str, ...]
    what_to_demonstrate: str = ""
    hard_blocker: bool = False
    evidence_requirement: EvidenceRequirement = EvidenceRequirement.DEFENSIBLE
    evidence_requirement_refs: tuple[str, ...] = ()
    temporal_requirement: TemporalRequirement = TemporalRequirement.NOT_REQUIRED
    temporal_requirement_refs: tuple[str, ...] = ()
    requirement_status: JobRequirementStatus = JobRequirementStatus.UNKNOWN
    substitutability: RequirementSubstitutability = RequirementSubstitutability.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.temporal_requirement, TemporalRequirement):
            raise ValueError("Invalid temporal requirement.")
        object.__setattr__(self, "temporal_requirement_refs", _refs(self.temporal_requirement_refs))
        if not isinstance(self.evidence_requirement, EvidenceRequirement):
            raise ValueError("Invalid evidence requirement.")
        object.__setattr__(self, "evidence_requirement_refs", _refs(self.evidence_requirement_refs))
        if not isinstance(self.requirement_status, JobRequirementStatus):
            raise ValueError("Invalid requirement status.")
        if not isinstance(self.substitutability, RequirementSubstitutability):
            raise ValueError("Invalid requirement substitutability.")
        object.__setattr__(self, "hard_fact_refs", _refs(self.hard_fact_refs))
        if not self.hard_fact_refs:
            raise ValueError("Interpreted job needs require hard-fact provenance.")
        if self.authority is not InterpretationAuthority.EXPLICIT and self.hard_blocker:
            raise ValueError("Only explicit hard facts may create a hard blocker.")
        if self.hard_blocker and self.requirement_status in {
            JobRequirementStatus.PREFERRED,
            JobRequirementStatus.USEFUL,
            JobRequirementStatus.EXPLICITLY_NOT_REQUIRED,
        }:
            raise ValueError("A non-required job need cannot be a hard blocker.")

    @property
    def performance_relevance(self) -> RequirementRelevance:
        return {
            RequirementImportance.CORE: RequirementRelevance.CORE,
            RequirementImportance.IMPORTANT: RequirementRelevance.SUPPORTING,
            RequirementImportance.NICE_TO_HAVE: RequirementRelevance.MINOR,
        }[self.importance]

    @property
    def is_non_substitutable_required(self) -> bool:
        return (
            self.authority is InterpretationAuthority.EXPLICIT
            and self.requirement_status is JobRequirementStatus.REQUIRED
            and self.substitutability is RequirementSubstitutability.NON_SUBSTITUTABLE
        )


@dataclass(frozen=True)
class AIJobProfileSnapshot:
    job_id: str
    profile_version: int
    job_signature: str
    created_at: str
    needs: tuple[InterpretedJobNeed, ...]
    problem_to_solve: str = ""
    responsibilities: tuple[str, ...] = ()
    context: str = ""
    uncertainties: tuple[str, ...] = ()
    tools_as_means: tuple[str, ...] = ()
    supersedes_version: int | None = None
    schema_version: str = AI_JOB_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _clean(self.job_id) or self.profile_version < 1:
            raise ValueError("Job profile identity and positive version are required.")
        if not _clean(self.job_signature) or not _clean(self.created_at):
            raise ValueError("Job profile signature and timestamp are required.")


@dataclass(frozen=True)
class RequirementLink:
    need_id: str
    evidence_state: RequirementEvidenceState
    evidence_refs: tuple[str, ...] = ()
    rationale: str = ""
    interview_defensible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))


@dataclass(frozen=True)
class CandidateProfileDraft:
    capabilities: tuple[ProfileCapability, ...]
    checkpoint: ProfileCheckpoint
    contexts: tuple[str, ...] = ()
    evidence_summaries: tuple[str, ...] = ()
    confirmed_gaps: tuple[str, ...] = ()
    evidence_gaps: tuple[str, ...] = ()
    objectives: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    seniority: str = ""
    responsibility_scope: str = ""
    structured_preferences: tuple[CandidatePreference, ...] = ()
    languages: tuple[CandidateLanguage, ...] = ()
    licences: tuple[CandidateLicence, ...] = ()
    work_authorizations: tuple[CandidateWorkAuthorization, ...] = ()
    fact_coverage: CandidateFactCoverage = field(default_factory=CandidateFactCoverage)


@dataclass(frozen=True)
class JobProfileDraft:
    needs: tuple[InterpretedJobNeed, ...]
    problem_to_solve: str = ""
    responsibilities: tuple[str, ...] = ()
    context: str = ""
    uncertainties: tuple[str, ...] = ()
    tools_as_means: tuple[str, ...] = ()


@dataclass(frozen=True)
class HiringCaseInterpretation:
    requirement_links: tuple[RequirementLink, ...]
    opportunity_signals: tuple[OpportunitySignal, ...] = ()
    seniority_context_mismatch: bool = False
    temporal_evidence: tuple[TemporalEvidenceMetadata, ...] = ()


@dataclass(frozen=True)
class TemporalEvidenceMetadata:
    ref: str
    need_id: str
    version: str = ""
    performed_on: str = ""
