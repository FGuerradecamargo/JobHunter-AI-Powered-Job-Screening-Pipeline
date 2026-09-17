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

    def __post_init__(self) -> None:
        if not isinstance(self.temporal_requirement, TemporalRequirement):
            raise ValueError("Invalid temporal requirement.")
        object.__setattr__(self, "temporal_requirement_refs", _refs(self.temporal_requirement_refs))
        if not isinstance(self.evidence_requirement, EvidenceRequirement):
            raise ValueError("Invalid evidence requirement.")
        object.__setattr__(self, "evidence_requirement_refs", _refs(self.evidence_requirement_refs))
        object.__setattr__(self, "hard_fact_refs", _refs(self.hard_fact_refs))
        if not self.hard_fact_refs:
            raise ValueError("Interpreted job needs require hard-fact provenance.")
        if self.authority is not InterpretationAuthority.EXPLICIT and self.hard_blocker:
            raise ValueError("Only explicit hard facts may create a hard blocker.")


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
