from models.prepare_application import PrepareApplicationResult
from services.application_contract_service import ApplicationAnalysisNotFoundError
from uuid import uuid4


PREPARATION_GENERATION_CLAIM_TTL_SECONDS = 900


class PrepareApplicationService:
    def __init__(
        self,
        *,
        contract_service,
        context_service,
        generation_service,
        claim_repository=None,
    ) -> None:
        self.contract_service = contract_service
        self.context_service = context_service
        self.generation_service = generation_service
        self.claim_repository = claim_repository

    def prepare(self, candidate_id: str, job_id: str) -> PrepareApplicationResult:
        candidate_id = str(candidate_id or "").strip()
        job_id = str(job_id or "").strip()
        if not candidate_id or not job_id:
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                error_code="invalid_request",
                error_message="Candidate and job are required.",
            )

        try:
            contract, analysis_source = self.contract_service.build_with_source(
                candidate_id,
                job_id,
            )
        except ApplicationAnalysisNotFoundError:
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                error_code="analysis_not_found",
                error_message="Analyzed opportunity was not found.",
            )
        except PermissionError:
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                error_code="scope_mismatch",
                error_message="Application preparation scope is invalid.",
            )
        except Exception:
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                error_code="contract_failed",
                error_message="Application contract could not be built.",
            )

        analysis_id = str(contract.analysis_id or "")
        if (
            contract.candidate_id != candidate_id
            or contract.job_id != job_id
            or analysis_source.candidate_id != candidate_id
            or analysis_source.job_id != job_id
            or analysis_source.analysis_id != contract.analysis_id
        ):
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                error_code="scope_mismatch",
                error_message="Application preparation scope is invalid.",
            )

        if not contract.eligible:
            return PrepareApplicationResult(
                status="ineligible",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                error_code="ineligible_application",
                error_message="This analyzed opportunity is not eligible.",
            )

        try:
            context = self.context_service.build_from_contract(
                contract,
                analysis_source,
            )
        except PermissionError:
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                error_code="scope_mismatch",
                error_message="Application context scope is invalid.",
            )
        except Exception:
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                error_code="context_failed",
                error_message="Application context could not be built.",
            )

        if (
            context.candidate_id != candidate_id
            or context.job_id != job_id
            or context.analysis_id != contract.analysis_id
            or context.contract_signature != contract.source_signature
        ):
            return PrepareApplicationResult(
                status="failed",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                error_code="scope_mismatch",
                error_message="Application context scope is invalid.",
            )

        claim_token = "preparation_generation_claim_" + uuid4().hex
        claim_acquired = False
        if self.claim_repository is not None:
            try:
                claim_acquired = self.claim_repository.acquire(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    application_context_signature=context.source_signature,
                    claim_token=claim_token,
                    ttl_seconds=PREPARATION_GENERATION_CLAIM_TTL_SECONDS,
                )
            except Exception:
                return PrepareApplicationResult(
                    status="generation_failed",
                    candidate_id=candidate_id,
                    job_id=job_id,
                    analysis_id=analysis_id,
                    application_context_signature=context.source_signature,
                    error_code="generation_claim_failed",
                    error_message="Application generation could not be reserved safely.",
                )
            if not claim_acquired:
                return PrepareApplicationResult(
                    status="generation_failed",
                    candidate_id=candidate_id,
                    job_id=job_id,
                    analysis_id=analysis_id,
                    application_context_signature=context.source_signature,
                    error_code="generation_in_progress",
                    error_message="Application generation is already in progress.",
                )

        try:
            try:
                generation = self.generation_service.generate(context)
            except Exception:
                return PrepareApplicationResult(
                    status="generation_failed",
                    candidate_id=candidate_id,
                    job_id=job_id,
                    analysis_id=analysis_id,
                    application_context_signature=context.source_signature,
                    error_code="generation_service_error",
                    error_message="Application material generation failed safely.",
                )
        finally:
            if claim_acquired:
                try:
                    self.claim_repository.release(
                        candidate_id=candidate_id,
                        job_id=job_id,
                        application_context_signature=context.source_signature,
                        claim_token=claim_token,
                    )
                except Exception:
                    pass

        if generation.status not in {"validated", "validated_after_repair"}:
            return PrepareApplicationResult(
                status="generation_failed",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                application_context_signature=context.source_signature,
                validation_issues=list(generation.validation_issues),
                error_code=generation.error_code or "generation_failed",
                error_message=(
                    generation.error_message
                    or "Application material generation was not validated."
                ),
                generation_status=generation.status,
            )

        if generation.cv is None:
            return PrepareApplicationResult(
                status="generation_failed",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                application_context_signature=context.source_signature,
                error_code="missing_validated_cv",
                error_message="Validated application material was not returned.",
                generation_status=generation.status,
            )

        if (
            generation.cv.candidate_id != candidate_id
            or generation.cv.job_id != job_id
            or generation.cv.application_context_signature
            != context.source_signature
        ):
            return PrepareApplicationResult(
                status="generation_failed",
                candidate_id=candidate_id,
                job_id=job_id,
                analysis_id=analysis_id,
                application_context_signature=context.source_signature,
                error_code="validated_cv_scope_mismatch",
                error_message="Validated application material has an invalid scope.",
                generation_status=generation.status,
            )

        return PrepareApplicationResult(
            status="prepared",
            candidate_id=candidate_id,
            job_id=job_id,
            analysis_id=analysis_id,
            application_context_signature=context.source_signature,
            cv=generation.cv,
            generation_status=generation.status,
        )
