from models.application_context import ApplicationContext
from models.tailored_cv_contract import TailoredCVGenerationResult
from services.tailored_cv_generation_request_builder import (
    build_tailored_cv_generation_request,
)
from services.tailored_cv_generator_client import TailoredCVGeneratorClient
from services.tailored_cv_parser import TailoredCVParseError, parse_tailored_cv_response
from services.tailored_cv_truth_guard import validate_tailored_cv_draft


class TailoredCVGenerationService:
    def __init__(self, generator_client: TailoredCVGeneratorClient) -> None:
        self.generator_client = generator_client

    def generate(self, context: ApplicationContext) -> TailoredCVGenerationResult:
        request = build_tailored_cv_generation_request(context)
        if not context.eligible or context.recommendation == "reject":
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="ineligible_application",
                error_message="Tailored CV generation requires an eligible application.",
                request_signature=request.source_signature,
            )
        if not request.selected_evidence:
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="no_selected_evidence",
                error_message="No selected evidence is available for CV generation.",
                request_signature=request.source_signature,
            )

        try:
            response = self.generator_client.generate(request)
            draft = parse_tailored_cv_response(response)
        except TailoredCVParseError as exc:
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="invalid_generator_output",
                error_message=str(exc),
                request_signature=request.source_signature,
            )
        except Exception:
            return TailoredCVGenerationResult(
                status="generation_error",
                error_code="generator_client_error",
                error_message="The generator client failed safely.",
                request_signature=request.source_signature,
            )

        validation = validate_tailored_cv_draft(draft, context)
        if not validation.valid:
            return TailoredCVGenerationResult(
                status="validation_failed",
                validation_issues=validation.issues,
                error_code="truth_guard_rejected",
                error_message="The generated draft failed truth validation.",
                request_signature=request.source_signature,
            )
        return TailoredCVGenerationResult(
            status="validated",
            cv=validation.normalized_draft,
            request_signature=request.source_signature,
        )
