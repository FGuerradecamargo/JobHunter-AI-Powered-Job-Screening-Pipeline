from dataclasses import dataclass, field

from models.application_contract import ApplicationEvidenceRef


@dataclass(frozen=True)
class PositioningTheme:
    theme: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ApplicationContext:
    candidate_id: str
    job_id: str
    analysis_id: str
    contract_signature: str
    job_title: str = ""
    company: str = ""
    role_family: str = ""
    job_level: str = ""
    core_requirements: list[str] = field(default_factory=list)
    direct_evidence: list[ApplicationEvidenceRef] = field(default_factory=list)
    transferable_evidence: list[ApplicationEvidenceRef] = field(
        default_factory=list
    )
    supporting_evidence: list[ApplicationEvidenceRef] = field(
        default_factory=list
    )
    developing_evidence: list[ApplicationEvidenceRef] = field(
        default_factory=list
    )
    available_evidence: list[ApplicationEvidenceRef] = field(
        default_factory=list
    )
    development_gaps: list[str] = field(default_factory=list)
    structural_gaps: list[str] = field(default_factory=list)
    positioning_themes: list[PositioningTheme] = field(default_factory=list)
    source_signature: str = ""
    schema_version: str = "application-context-v1"
    authority: str = "derived_application_selection"

