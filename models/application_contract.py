from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ApplicationEvidenceRef:
    evidence_ref: str
    source_type: str
    source_id: str
    authority: str
    statement: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicationContract:
    candidate_id: str
    job_id: str
    analysis_id: str
    recommendation: str
    eligible: bool
    evidence_refs: list[ApplicationEvidenceRef] = field(default_factory=list)
    development_gaps: list[str] = field(default_factory=list)
    structural_gaps: list[str] = field(default_factory=list)
    source_signature: str = ""
    schema_version: str = "application-contract-v1"
    authority: str = "derived_evidence_boundary"


@dataclass(frozen=True)
class ApplicationAnalysisSource:
    candidate_id: str
    job_id: str
    analysis_id: str
    recommendation: str
    job: dict[str, Any]
    analysis: dict[str, Any]

