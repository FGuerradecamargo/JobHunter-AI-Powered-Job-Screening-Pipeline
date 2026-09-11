from dataclasses import dataclass, field

from models.tailored_cv_contract import CVValidationIssue, DraftTailoredCV


@dataclass(frozen=True)
class PrepareApplicationResult:
    status: str
    candidate_id: str
    job_id: str
    analysis_id: str = ""
    application_context_signature: str = ""
    cv: DraftTailoredCV | None = None
    validation_issues: list[CVValidationIssue] = field(default_factory=list)
    error_code: str = ""
    error_message: str = ""
    generation_status: str = ""
