"""Content-free diagnostics: never serialize drafts, exceptions or issue messages."""

import json
import logging


ISSUE_REASONS = {
    "candidate_mismatch": "Generated CV scope did not match this application.",
    "job_mismatch": "Generated CV scope did not match this application.",
    "context_signature_mismatch": "Generated CV scope did not match this application.",
    "unknown_evidence_ref": "Unsupported evidence reference detected.",
    "missing_evidence_ref": "Required evidence references were missing.",
    "experience_source_mismatch": "Experience evidence did not match its source.",
    "developing_evidence_overclaim": "Developing knowledge was presented as established expertise.",
    "transferable_evidence_overclaim": "Transferable evidence was presented as direct experience.",
    "insufficient_evidence_authority": "Evidence could not support the claim type.",
    "protected_gap_conflict": "A claim conflicted with a protected evidence gap.",
    "invalid_claim_type": "Generated CV claim type was invalid.",
    "empty_statement": "Generated CV contained an empty statement.",
}

ERROR_STAGES = {
    "ineligible_application": "preflight",
    "no_selected_evidence": "preflight",
    "invalid_generator_output": "initial_parse",
    "generator_client_error": "initial_client",
    "truth_guard_rejected": "initial_truth_guard",
    "invalid_repair_output": "repair_parse",
    "repair_client_error": "repair_client",
    "repair_exhausted": "repair_truth_guard",
}


def log_cv_diagnostic(*, stage, issues=(), error_code="", repair_attempted=False):
    codes = sorted({item.code if item.code in ISSUE_REASONS else "unknown_issue" for item in issues})
    payload = {
        "event": "tailored_cv_validation",
        "stage": stage if stage in set(ERROR_STAGES.values()) | {"validated", "validated_after_repair", "internal_error"} else "unknown_stage",
        "error_code": error_code if error_code in ERROR_STAGES else "",
        "validation_codes": codes,
        "issue_count": len(issues),
        "repair_attempted": bool(repair_attempted),
    }
    logging.getLogger(__name__).warning("%s", json.dumps(payload, sort_keys=True))


def validation_failure_message(result):
    prefix = "Tailored CV could not be validated."
    if result.error_code in {"invalid_generator_output", "invalid_repair_output"}:
        reason = "Generated CV structure was invalid."
    else:
        reasons = dict.fromkeys(ISSUE_REASONS[item.code] for item in result.validation_issues if item.code in ISSUE_REASONS)
        reason = " ".join(reasons) or "The draft did not satisfy validation requirements."
    if result.error_code in {"repair_exhausted", "invalid_repair_output"}:
        reason = "Repair attempt also failed validation. " + reason
    return prefix + " " + reason
