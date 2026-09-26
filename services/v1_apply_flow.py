"""V1 orchestration boundary. Inject existing preparation/claim orchestration."""
from dataclasses import replace

from models.prepare_application import PrepareApplicationResult
from models.cv_preparation_progress import CVPreparationStage as Stage, CVPreparationStageState as State, progress_event
from services.tailored_cv_edit_service import validate_edited_cv
from services.external_application import external_application_url
from services.prepared_cv_exporter import export_prepared_cv_docx


def validate_apply_sources(*, candidate_profile, job_profile, hiring_case, context):
    if not (candidate_profile.candidate_id == hiring_case.candidate_id == context.candidate_id
            and job_profile.job_id == hiring_case.job_id == context.job_id):
        raise PermissionError("Application source scope mismatch.")
    if (hiring_case.candidate_profile_version != candidate_profile.profile_version
            or hiring_case.job_profile_version != job_profile.profile_version
            or hiring_case.candidate_signature != candidate_profile.memory_signature
            or hiring_case.job_signature != job_profile.job_signature):
        raise ValueError("Application source versions are stale.")
    if hiring_case.hard_eligibility_blockers or not context.eligible:
        raise ValueError("Application is not eligible.")
    if any(e.evidence_ref not in candidate_profile.source_refs for e in context.available_evidence):
        raise ValueError("Application evidence is outside the candidate snapshot.")


class V1ApplyFlow:
    def __init__(self, *, preparation_service, lifecycle_service):
        self.preparation = preparation_service
        self.lifecycle = lifecycle_service

    def prepare(self, *, candidate_profile, job_profile, hiring_case, context, progress=None):
        validate_apply_sources(candidate_profile=candidate_profile, job_profile=job_profile,
                               hiring_case=hiring_case, context=context)
        emit = progress or (lambda event: None)
        emit(progress_event(Stage.MATCHING_EVIDENCE, State.COMPLETE))
        emit(progress_event(Stage.ADAPTING_LANGUAGE, State.ACTIVE))
        result = self.preparation.prepare(context.candidate_id, context.job_id)
        if result.candidate_id != context.candidate_id or result.job_id != context.job_id:
            raise PermissionError("Prepared application scope mismatch.")
        if result.cv is None or result.status != "prepared":
            emit(progress_event(Stage.ADAPTING_LANGUAGE, State.FAILED))
            return result
        emit(progress_event(Stage.ADAPTING_LANGUAGE, State.COMPLETE))
        emit(progress_event(Stage.CHECKING_ATS_KEYWORDS, State.ACTIVE))
        validation = validate_edited_cv(draft=result.cv, context=context)
        emit(progress_event(Stage.CHECKING_ATS_KEYWORDS, State.COMPLETE))
        emit(progress_event(Stage.KEEPING_DEFENSIBLE, State.COMPLETE if validation.accepted else State.FAILED))
        if not validation.accepted:
            return replace(result, status="generation_failed", cv=None,
                           validation_issues=validation.issues, error_code="truth_guard_rejected")
        return result

    def edit(self, *, draft, context):
        return validate_edited_cv(draft=draft, context=context)

    def export(self, *, draft, context, candidate_name, company, role):
        validation = validate_edited_cv(draft=draft, context=context)
        if not validation.accepted:
            raise ValueError("CV contains unsupported content; review validation issues before export.")
        result = PrepareApplicationResult(status="prepared", candidate_id=context.candidate_id,
            job_id=context.job_id, application_context_signature=context.source_signature,
            cv=validation.cv, generation_status="validated")
        return export_prepared_cv_docx(result, candidate_name=candidate_name, company=company, role=role)

    def ready(self, *, draft, context):
        if not validate_edited_cv(draft=draft, context=context).accepted:
            raise ValueError("A defensible CV is required.")
        return self.lifecycle.mark_ready_to_apply(context.candidate_id, context.job_id)

    def open_external(self, url):
        # Return a URL for a UI link. No submission and no lifecycle write.
        return external_application_url(url)

    def confirm_applied(self, *, candidate_id, job_id, confirmed):
        if confirmed is not True:
            return None
        return self.lifecycle.mark_applied(candidate_id, job_id)
