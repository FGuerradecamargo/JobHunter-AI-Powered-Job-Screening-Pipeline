from __future__ import annotations

import re

from models.interview_context import InterviewContext, InterviewDetails
from models.interview_prep_contract import InterviewPrepContract
from services.career_memory_source_builder import build_source_signature


INTERVIEW_CONTEXT_SCHEMA_VERSION = "interview-context-v1"


def _display(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _canonical_text(value) -> str:
    return _display(value).casefold()


def _canonical_topics(values) -> list[str]:
    return sorted({_canonical_text(value) for value in values if _display(value)})


def build_interview_context(
    *,
    contract: InterviewPrepContract,
    details: InterviewDetails | None = None,
) -> InterviewContext:
    if not contract.eligible:
        raise ValueError("Interview Prep Contract is not eligible.")
    if details is not None and details.candidate_id != contract.candidate_id:
        raise PermissionError("Interview details belong to another candidate.")
    if details is not None and details.job_id != contract.job_id:
        raise PermissionError("Interview details belong to another job.")

    details = details or InterviewDetails(
        candidate_id=contract.candidate_id,
        job_id=contract.job_id,
    )
    topics_by_key = {}
    for value in details.explicit_topics:
        display = _display(value)
        if display:
            topics_by_key.setdefault(display.casefold(), display)
    topics = [topics_by_key[key] for key in sorted(topics_by_key)]
    evidence = sorted(contract.authorized_evidence, key=lambda item: item.evidence_ref)
    themes = sorted(contract.positioning_themes, key=lambda item: item.theme.casefold())
    signature_payload = {
        "schema_version": INTERVIEW_CONTEXT_SCHEMA_VERSION,
        "interview_prep_contract_signature": contract.source_signature,
        "interview_stage": _canonical_text(contract.interview_stage),
        "details": {
            "interview_type": _canonical_text(details.interview_type),
            "interview_format": _canonical_text(details.interview_format),
            "interviewer": _canonical_text(details.interviewer),
            "duration_minutes": details.duration_minutes,
            "scheduled_at": _canonical_text(details.scheduled_at),
            "instructions": _canonical_text(details.instructions),
            "explicit_topics": _canonical_topics(details.explicit_topics),
        },
    }
    return InterviewContext(
        candidate_id=contract.candidate_id,
        job_id=contract.job_id,
        analysis_id=contract.analysis_id,
        interview_prep_contract_signature=contract.source_signature,
        interview_stage=contract.interview_stage,
        job_title=contract.job_title,
        company=contract.company,
        role_family=contract.role_family,
        job_level=contract.job_level,
        interview_type=_display(details.interview_type),
        interview_format=_display(details.interview_format),
        interviewer=_display(details.interviewer),
        duration_minutes=details.duration_minutes,
        scheduled_at=_display(details.scheduled_at),
        instructions=details.instructions.strip(),
        explicit_topics=topics,
        core_requirements=list(contract.target_requirements),
        authorized_evidence=evidence,
        positioning_themes=themes,
        development_gaps=list(contract.development_gaps),
        structural_gaps=list(contract.protected_structural_gaps),
        source_signature=build_source_signature(signature_payload),
        schema_version=INTERVIEW_CONTEXT_SCHEMA_VERSION,
    )
