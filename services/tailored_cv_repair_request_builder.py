from dataclasses import asdict
import json

from models.tailored_cv_contract import (
    CVValidationIssue,
    DraftTailoredCV,
    TailoredCVGenerationRequest,
    TailoredCVRepairRequest,
)
from services.career_memory_source_builder import build_source_signature


_REPAIR_INSTRUCTIONS = """The previous tailored CV output failed validation.
Correct only the invalid parts and preserve valid statements where possible.
Use only the authorized evidence refs supplied in this request.
Do not invent replacement evidence.
Do not convert transferable or developing evidence into professional fact.
Preserve candidate_id, job_id, application_context_signature, and source_experience_id.
Correct or remove unsupported statements without creating new claims.
Return JSON only, conforming exactly to tailored-cv-v1."""


def build_tailored_cv_repair_request(
    *,
    original_request: TailoredCVGenerationRequest,
    previous_draft: DraftTailoredCV,
    validation_issues: list[CVValidationIssue],
) -> TailoredCVRepairRequest:
    issues = sorted(
        (asdict(item) for item in validation_issues),
        key=lambda item: (item["code"], item["location"], item["message"]),
    )
    payload = {
        "candidate_id": original_request.candidate_id,
        "job_id": original_request.job_id,
        "application_context_signature": (
            original_request.application_context_signature
        ),
        "original_request_signature": original_request.source_signature,
        "previous_draft": asdict(previous_draft),
        "validation_issues": issues,
        "selected_evidence": list(original_request.selected_evidence),
        "protected_structural_gaps": list(
            original_request.protected_structural_gaps
        ),
        "output_schema_version": original_request.output_schema_version,
    }
    prompt = _REPAIR_INSTRUCTIONS + "\n\nREPAIR_INPUT:\n" + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    signature = build_source_signature(
        {
            "schema_version": "tailored-cv-repair-request-v1",
            "instructions": _REPAIR_INSTRUCTIONS,
            "payload": payload,
        }
    )
    return TailoredCVRepairRequest(
        candidate_id=original_request.candidate_id,
        job_id=original_request.job_id,
        application_context_signature=(
            original_request.application_context_signature
        ),
        original_request_signature=original_request.source_signature,
        previous_draft=payload["previous_draft"],
        validation_issues=issues,
        selected_evidence=list(original_request.selected_evidence),
        protected_structural_gaps=list(
            original_request.protected_structural_gaps
        ),
        output_schema_version=original_request.output_schema_version,
        prompt=prompt,
        source_signature=signature,
    )
