from models.application_context import ApplicationContext
from models.tailored_cv_contract import TailoredCVGenerationResult
from services.tailored_cv_generation_request_builder import (
    build_tailored_cv_generation_request,
)
from services.tailored_cv_generator_client import TailoredCVGeneratorClient
from services.tailored_cv_parser import TailoredCVParseError, parse_tailored_cv_response
from services.tailored_cv_repair_request_builder import (
    build_tailored_cv_repair_request,
)
from services.tailored_cv_truth_guard import validate_tailored_cv_draft
from services.tailored_cv_diagnostics import ERROR_STAGES, log_cv_diagnostic


_REPAIRABLE_ISSUE_CODES = {
    "unknown_evidence_ref",
    "missing_evidence_ref",
    "experience_source_mismatch",
    "developing_evidence_overclaim",
    "transferable_evidence_overclaim",
    "insufficient_evidence_authority",
    "protected_gap_conflict",
    "invalid_claim_type",
    "empty_statement",
}


def _is_repairable(validation) -> bool:
    issue_codes = {item.code for item in validation.issues}
    return bool(issue_codes) and issue_codes.issubset(_REPAIRABLE_ISSUE_CODES)


class TailoredCVGenerationService:
    def __init__(
        self,
        generator_client: TailoredCVGeneratorClient,
        *,
        max_repair_attempts: int = 1,
    ) -> None:
        if max_repair_attempts not in {0, 1}:
            raise ValueError("max_repair_attempts must be zero or one.")
        self.generator_client = generator_client
        self.max_repair_attempts = max_repair_attempts

    def generate(self, context: ApplicationContext) -> TailoredCVGenerationResult:
        result = self._generate(context)
        if result.status != "validated":
            log_cv_diagnostic(
                stage=ERROR_STAGES.get(result.error_code, result.status),
                issues=result.validation_issues,
                error_code=result.error_code,
                repair_attempted=result.attempt_count > 1,
            )
        return result

    def _generate(self, context: ApplicationContext) -> TailoredCVGenerationResult:
        request = build_tailored_cv_generation_request(context)
        if not context.eligible or context.recommendation == "reject":
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="ineligible_application",
                error_message="Tailored CV generation requires an eligible application.",
                request_signature=request.source_signature,
                attempt_count=0,
            )
        if not request.selected_evidence:
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="no_selected_evidence",
                error_message="No selected evidence is available for CV generation.",
                request_signature=request.source_signature,
                attempt_count=0,
            )

        try:
            response = self.generator_client.generate(request)
            draft = parse_tailored_cv_response(response)
        except TailoredCVParseError as exc:
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="invalid_generator_output",
                error_message="The generated CV structure was invalid.",
                request_signature=request.source_signature,
                attempt_count=1,
            )
        except Exception:
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="generator_client_error",
                error_message="The generator client failed safely.",
                request_signature=request.source_signature,
                attempt_count=1,
            )

        validation = validate_tailored_cv_draft(draft, context)
        if validation.valid:
            return TailoredCVGenerationResult(
                status="validated",
                cv=validation.normalized_draft,
                request_signature=request.source_signature,
                attempt_count=1,
            )

        if not _is_repairable(validation) or self.max_repair_attempts == 0:
            return TailoredCVGenerationResult(
                status="validation_failed",
                validation_issues=validation.issues,
                error_code="truth_guard_rejected",
                error_message="The generated draft failed truth validation.",
                request_signature=request.source_signature,
                attempt_count=1,
            )

        repair_signature = ""
        log_cv_diagnostic(stage="initial_truth_guard", issues=validation.issues)
        attempts = 1
        for _ in range(self.max_repair_attempts):
            repair_request = build_tailored_cv_repair_request(
                original_request=request,
                previous_draft=validation.normalized_draft,
                validation_issues=validation.issues,
            )
            repair_signature = repair_request.source_signature
            attempts += 1
            try:
                response = self.generator_client.generate(repair_request)
                draft = parse_tailored_cv_response(response)
            except TailoredCVParseError as exc:
                return TailoredCVGenerationResult(
                    status="repair_failed",
                    error_code="invalid_repair_output",
                    error_message="The repaired CV structure was invalid.",
                    request_signature=request.source_signature,
                    repair_signature=repair_signature,
                    attempt_count=attempts,
                )
            except Exception:
                return TailoredCVGenerationResult(
                    status="repair_failed",
                    error_code="repair_client_error",
                    error_message="The repair client failed safely.",
                    request_signature=request.source_signature,
                    repair_signature=repair_signature,
                    attempt_count=attempts,
                )

            validation = validate_tailored_cv_draft(draft, context)
            if validation.valid:
                return TailoredCVGenerationResult(
                    status="validated_after_repair",
                    cv=validation.normalized_draft,
                    request_signature=request.source_signature,
                    repair_signature=repair_signature,
                    attempt_count=attempts,
                )
            if not _is_repairable(validation):
                break

        return TailoredCVGenerationResult(
            status="validation_failed",
            validation_issues=validation.issues,
            error_code="repair_exhausted",
            error_message="The repaired draft failed truth validation.",
            request_signature=request.source_signature,
            repair_signature=repair_signature,
            attempt_count=attempts,
        )
