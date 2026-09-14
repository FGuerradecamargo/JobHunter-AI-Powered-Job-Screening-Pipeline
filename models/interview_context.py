from dataclasses import dataclass, field

from models.application_context import PositioningTheme
from models.application_contract import ApplicationEvidenceRef


@dataclass(frozen=True)
class InterviewDetails:
    candidate_id: str
    job_id: str
    interview_type: str = ""
    interview_format: str = ""
    interviewer: str = ""
    duration_minutes: int | None = None
    scheduled_at: str = ""
    instructions: str = ""
    explicit_topics: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class InterviewContext:
    candidate_id: str
    job_id: str
    analysis_id: str
    interview_prep_contract_signature: str
    interview_stage: str

    job_title: str = ""
    company: str = ""
    role_family: str = ""
    job_level: str = ""

    interview_type: str = ""
    interview_format: str = ""
    interviewer: str = ""
    duration_minutes: int | None = None
    scheduled_at: str = ""
    instructions: str = ""
    explicit_topics: list[str] = field(default_factory=list)

    core_requirements: list[str] = field(default_factory=list)
    authorized_evidence: list[ApplicationEvidenceRef] = field(default_factory=list)
    positioning_themes: list[PositioningTheme] = field(default_factory=list)
    development_gaps: list[str] = field(default_factory=list)
    structural_gaps: list[str] = field(default_factory=list)

    source_signature: str = ""
    schema_version: str = "interview-context-v1"
    authority: str = "derived_interview_context"
