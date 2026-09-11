from dataclasses import dataclass, field


@dataclass(frozen=True)
class TailoredCVStatement:
    text: str
    claim_type: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DraftTailoredCVExperience:
    source_experience_id: str
    company: str
    role: str
    bullets: list[TailoredCVStatement] = field(default_factory=list)


@dataclass(frozen=True)
class DraftTailoredCV:
    candidate_id: str
    job_id: str
    application_context_signature: str
    headline: TailoredCVStatement
    professional_summary: list[TailoredCVStatement] = field(default_factory=list)
    key_skills: list[TailoredCVStatement] = field(default_factory=list)
    experiences: list[DraftTailoredCVExperience] = field(default_factory=list)
    additional_relevant_information: list[TailoredCVStatement] = field(
        default_factory=list
    )
    schema_version: str = "tailored-cv-v1"


@dataclass(frozen=True)
class CVValidationIssue:
    code: str
    location: str
    message: str


@dataclass(frozen=True)
class CVValidationResult:
    valid: bool
    issues: list[CVValidationIssue] = field(default_factory=list)
    normalized_draft: DraftTailoredCV | None = None
    draft_signature: str = ""
    protected_structural_gaps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TailoredCVGenerationRequest:
    candidate_id: str
    job_id: str
    application_context_signature: str
    job_title: str
    company: str
    role_family: str
    job_level: str
    core_requirements: list[str] = field(default_factory=list)
    selected_evidence: list[dict] = field(default_factory=list)
    development_gaps: list[str] = field(default_factory=list)
    protected_structural_gaps: list[str] = field(default_factory=list)
    allowed_claim_types: list[str] = field(default_factory=list)
    output_schema_version: str = "tailored-cv-v1"
    prompt: str = ""
    source_signature: str = ""
    schema_version: str = "tailored-cv-generation-request-v1"


@dataclass(frozen=True)
class TailoredCVRepairRequest:
    candidate_id: str
    job_id: str
    application_context_signature: str
    original_request_signature: str
    previous_draft: dict
    validation_issues: list[dict] = field(default_factory=list)
    selected_evidence: list[dict] = field(default_factory=list)
    protected_structural_gaps: list[str] = field(default_factory=list)
    output_schema_version: str = "tailored-cv-v1"
    prompt: str = ""
    source_signature: str = ""
    schema_version: str = "tailored-cv-repair-request-v1"


@dataclass(frozen=True)
class TailoredCVGenerationResult:
    status: str
    cv: DraftTailoredCV | None = None
    validation_issues: list[CVValidationIssue] = field(default_factory=list)
    error_code: str = ""
    error_message: str = ""
    request_signature: str = ""
    repair_signature: str = ""
    attempt_count: int = 0
