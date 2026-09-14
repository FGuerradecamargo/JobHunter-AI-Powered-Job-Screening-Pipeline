from dataclasses import dataclass, field

from models.application_context import PositioningTheme
from models.application_contract import ApplicationEvidenceRef


@dataclass(frozen=True)
class InterviewPrepContract:
    candidate_id: str
    job_id: str
    analysis_id: str
    application_context_signature: str
    interview_stage: str
    application_final_status: str
    eligible: bool

    job_title: str = ""
    company: str = ""
    role_family: str = ""
    job_level: str = ""
    authorized_evidence: list[ApplicationEvidenceRef] = field(default_factory=list)
    development_gaps: list[str] = field(default_factory=list)
    protected_structural_gaps: list[str] = field(default_factory=list)
    target_requirements: list[str] = field(default_factory=list)
    positioning_themes: list[PositioningTheme] = field(default_factory=list)

    source_signature: str = ""
    schema_version: str = "interview-prep-contract-v1"
    authority: str = "derived_evidence_boundary"
