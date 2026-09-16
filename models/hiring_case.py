from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


HIRING_CASE_SCHEMA_VERSION = "hiring-case-v1"
EVIDENCE_WARNING = (
    "This may be added to Career Memory and reused in future matches, CVs and "
    "interview preparation. Only add real experience you can explain and defend."
)


class RequirementEvidenceState(str, Enum):
    PROVEN = "proven"
    TRANSFERABLE = "transferable"
    EVIDENCE_MISSING = "evidence_missing"
    GAP = "gap"


class RequirementImportance(str, Enum):
    CORE = "core"
    IMPORTANT = "important"
    NICE_TO_HAVE = "nice_to_have"


class HiringCaseStrength(str, Enum):
    STRONG = "strong"
    VIABLE = "viable"
    WEAK = "weak"
    INELIGIBLE = "ineligible"


class OpportunityValue(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OpportunityConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OpportunitySignalState(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class OpportunitySignalKind(str, Enum):
    COMPENSATION = "compensation"
    CAREER_DIRECTION = "career_direction"
    GROWTH = "growth"
    SENIORITY_PROGRESSION = "seniority_progression"
    WORK_MODE_LOCATION = "work_mode_location"
    ROLE_CONTENT = "role_content"
    STRATEGIC_VALUE = "strategic_value"
    TRADE_OFF = "trade_off"
    OBJECTIVE_TIMING = "objective_timing"


class HiringCaseClassification(str, Enum):
    BEST_MATCH = "best_match"
    WORTH_A_TRY = "worth_a_try"
    YOURE_STRONG_BUT = "youre_strong_but"
    SKIP_FOR_NOW = "skip_for_now"
    INELIGIBLE = "ineligible"


class ExperienceAnswer(str, Enum):
    YES = "yes"
    NO = "no"


def _clean(value: str, *, maximum: int = 240) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _refs(values: list[str]) -> list[str]:
    return sorted({_clean(value, maximum=160) for value in values if _clean(value)})


@dataclass(frozen=True)
class RequirementAssessment:
    requirement_id: str
    requirement: str
    importance: RequirementImportance
    evidence_state: RequirementEvidenceState
    evidence_refs: list[str] = field(default_factory=list)
    rationale: str = ""
    interview_defensible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_id", _clean(self.requirement_id, maximum=160))
        object.__setattr__(self, "requirement", _clean(self.requirement))
        object.__setattr__(self, "rationale", _clean(self.rationale))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        if not self.requirement_id or not self.requirement:
            raise ValueError("Requirement identity and text are required.")
        has_evidence = bool(self.evidence_refs)
        if self.evidence_state in {
            RequirementEvidenceState.PROVEN,
            RequirementEvidenceState.TRANSFERABLE,
        } and not has_evidence:
            raise ValueError("Proven or transferable support requires evidence refs.")
        if self.interview_defensible and not has_evidence:
            raise ValueError("Interview-defensible support requires evidence refs.")
        if self.evidence_state in {
            RequirementEvidenceState.EVIDENCE_MISSING,
            RequirementEvidenceState.GAP,
        } and self.interview_defensible:
            raise ValueError("Missing evidence or a gap is not interview-defensible.")


@dataclass(frozen=True)
class OpportunitySignal:
    kind: OpportunitySignalKind
    state: OpportunitySignalState
    importance: RequirementImportance
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rationale", _clean(self.rationale))


@dataclass(frozen=True)
class OpportunityAssessment:
    value: OpportunityValue
    confidence: OpportunityConfidence
    signals: list[OpportunitySignal] = field(default_factory=list)


@dataclass(frozen=True)
class ProofItem:
    requirement_id: str
    what_they_need: str
    evidence_we_have: list[str]
    evidence_state: RequirementEvidenceState
    what_to_demonstrate: str
    needs_evidence: bool
    interview_defensible: bool


@dataclass(frozen=True)
class HowToProveContract:
    items: list[ProofItem] = field(default_factory=list)
    schema_version: str = "how-to-prove-v1"


@dataclass(frozen=True)
class StructuredEvidenceDraft:
    context: str
    candidate_action: str
    tools_or_methods: str
    result_or_impact: str
    timeframe_or_source: str = ""
    warning_acknowledged: bool = False

    def __post_init__(self) -> None:
        for name in (
            "context",
            "candidate_action",
            "tools_or_methods",
            "result_or_impact",
        ):
            value = _clean(getattr(self, name), maximum=1000)
            object.__setattr__(self, name, value)
            if not value:
                raise ValueError(f"Structured evidence {name} is required.")
        object.__setattr__(
            self,
            "timeframe_or_source",
            _clean(self.timeframe_or_source, maximum=240),
        )


@dataclass(frozen=True)
class AddEvidenceContract:
    requirement_id: str
    question: str
    answer: ExperienceAnswer | None = None
    structured_evidence: StructuredEvidenceDraft | None = None
    warning: str = EVIDENCE_WARNING
    confirmation_required: bool = True
    schema_version: str = "add-evidence-contract-v1"

    def __post_init__(self) -> None:
        if self.answer is ExperienceAnswer.NO and self.structured_evidence is not None:
            raise ValueError("A no answer must not collect structured evidence.")
        if self.answer is ExperienceAnswer.YES and self.structured_evidence is not None:
            if not self.structured_evidence.warning_acknowledged:
                raise ValueError("Evidence reuse warning must be acknowledged.")


@dataclass(frozen=True)
class HiringCaseInput:
    candidate_id: str
    job_id: str
    requirements: list[RequirementAssessment]
    opportunity_signals: list[OpportunitySignal] = field(default_factory=list)
    hard_eligibility_blockers: list[str] = field(default_factory=list)
    seniority_context_mismatch: bool = False


@dataclass(frozen=True)
class HiringCase:
    candidate_id: str
    job_id: str
    requirements: list[RequirementAssessment]
    hiring_case_strength: HiringCaseStrength
    opportunity: OpportunityAssessment
    classification: HiringCaseClassification
    how_to_prove: HowToProveContract
    add_evidence: list[AddEvidenceContract] = field(default_factory=list)
    hard_eligibility_blockers: list[str] = field(default_factory=list)
    schema_version: str = HIRING_CASE_SCHEMA_VERSION
    authority: str = "deterministic_hiring_case"
