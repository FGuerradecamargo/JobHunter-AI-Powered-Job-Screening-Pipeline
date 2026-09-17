"""Private, provider-neutral semantic interpretation. No inferred facts or reasoning trace."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from models.hiring_case import RequirementEvidenceState, TemporalApplicability
from models.profile_interpretation import SourceEvidence
from models.structured_interpretation import LinkConfidence, StructuredInterpretationInput, ValidationStatus


class SemanticSupportRelation(str, Enum):
    DIRECT = "direct"
    ADJACENT = "adjacent"
    NONE = "none"
    UNCERTAIN = "uncertain"


class SemanticCoverage(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"
    UNKNOWN = "unknown"


class SemanticReason(str, Enum):
    DIRECT_SUPPORT = "direct_support"
    ADJACENT_SUPPORT = "adjacent_support"
    NO_SUPPORT = "no_support"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    CONFLICTING_SOURCES = "conflicting_sources"
    PARTIAL_SUPPORT = "partial_support"
    JOINT_SUPPORT = "joint_support"


class SourceAuthority(str, Enum):
    SOURCE_FACT = "source_fact"


@dataclass(frozen=True)
class SemanticEvidenceLink:
    need_id: str
    evidence_ref: str
    candidate_capability_id: str | None
    support_relation: SemanticSupportRelation
    coverage: SemanticCoverage
    confidence: LinkConfidence
    reason_code: SemanticReason
    interpreter_version: str
    source_authority: SourceAuthority = SourceAuthority.SOURCE_FACT


@dataclass(frozen=True)
class NeedSemanticSupport:
    need_id: str
    links: tuple[SemanticEvidenceLink, ...]
    support_relation: SemanticSupportRelation
    coverage: SemanticCoverage
    confidence: LinkConfidence
    reason_code: SemanticReason
    # Explicit interpreter judgment, never inferred from the number of references.
    joint_support: bool = False
    evidence_question_hint: str = ""


@dataclass(frozen=True)
class SemanticSupportRequest:
    context: StructuredInterpretationInput
    evidence: tuple[SourceEvidence, ...]
    schema_version: str = "semantic-support-request-v1"


@dataclass(frozen=True)
class SemanticSupportResponse:
    input_signature: str
    interpreter_version: str
    needs: tuple[NeedSemanticSupport, ...]
    schema_version: str = "semantic-support-response-v1"


@dataclass(frozen=True)
class ResolvedSemanticSupport:
    support: NeedSemanticSupport
    assessment: RequirementEvidenceState
    supporting_refs: tuple[str, ...]
    temporal_applicability: TemporalApplicability


@dataclass(frozen=True)
class SemanticSupportResult:
    input_signature: str
    status: ValidationStatus
    needs: tuple[ResolvedSemanticSupport, ...] = ()
    issue_codes: tuple[str, ...] = ()


class SemanticSupportInterpreter(Protocol):
    def evaluate_semantic_support(self, request: SemanticSupportRequest) -> SemanticSupportResponse | dict | None: ...
