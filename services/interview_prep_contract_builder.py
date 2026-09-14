from __future__ import annotations

from dataclasses import asdict
import re

from models.application_context import ApplicationContext
from models.interview_prep_contract import InterviewPrepContract
from services.career_memory_source_builder import build_source_signature


INTERVIEW_PREP_CONTRACT_SCHEMA_VERSION = "interview-prep-contract-v1"
INTERVIEW_PREP_ELIGIBLE_STAGES = {"interview", "final_interview"}


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _canonical(value):
    if isinstance(value, dict):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: build_source_signature({"item": item}))
    if isinstance(value, str):
        return _normalize(value)
    return value


def build_interview_prep_contract(
    *,
    context: ApplicationContext,
    interview_stage: str,
    eligible: bool,
    application_final_status: str = "",
) -> InterviewPrepContract:
    normalized_stage = _normalize(interview_stage).casefold()
    normalized_final_status = _normalize(application_final_status).casefold()
    expected_eligible = bool(
        not normalized_final_status
        and normalized_stage in INTERVIEW_PREP_ELIGIBLE_STAGES
    )
    if eligible != expected_eligible:
        raise ValueError("Interview Prep eligibility does not match its stage.")

    evidence = sorted(
        context.available_evidence,
        key=lambda item: item.evidence_ref,
    )
    themes = sorted(
        context.positioning_themes,
        key=lambda item: item.theme.casefold(),
    )
    signature_payload = _canonical(
        {
            "schema_version": INTERVIEW_PREP_CONTRACT_SCHEMA_VERSION,
            "candidate_id": context.candidate_id,
            "job_id": context.job_id,
            "analysis_id": context.analysis_id,
            "application_context_signature": context.source_signature,
            "interview_stage": normalized_stage,
            "application_final_status": normalized_final_status,
            "authorized_evidence": [asdict(item) for item in evidence],
            "development_gaps": context.development_gaps,
            "protected_structural_gaps": context.structural_gaps,
            "target_requirements": context.core_requirements,
            "positioning_themes": [asdict(item) for item in themes],
        }
    )
    return InterviewPrepContract(
        candidate_id=context.candidate_id,
        job_id=context.job_id,
        analysis_id=context.analysis_id,
        application_context_signature=context.source_signature,
        interview_stage=normalized_stage,
        application_final_status=normalized_final_status,
        eligible=eligible,
        job_title=context.job_title,
        company=context.company,
        role_family=context.role_family,
        job_level=context.job_level,
        authorized_evidence=evidence,
        development_gaps=list(context.development_gaps),
        protected_structural_gaps=list(context.structural_gaps),
        target_requirements=list(context.core_requirements),
        positioning_themes=themes,
        source_signature=build_source_signature(signature_payload),
        schema_version=INTERVIEW_PREP_CONTRACT_SCHEMA_VERSION,
    )
