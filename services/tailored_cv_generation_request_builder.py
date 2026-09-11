from dataclasses import asdict
import json

from models.application_context import ApplicationContext
from models.tailored_cv_contract import TailoredCVGenerationRequest
from services.career_memory_source_builder import build_source_signature


ALLOWED_CLAIM_TYPES = (
    "professional_experience",
    "transferable_capability",
    "skill",
    "developing_knowledge",
    "summary",
)

_INSTRUCTIONS = """You are not creating a candidate.
You are selecting and communicating existing evidence for this opportunity.
Return JSON only, conforming exactly to tailored-cv-v1.
Every statement must contain text, claim_type, and evidence_refs.
Every experience must preserve source_experience_id.
Do not invent responsibilities, technologies, metrics, or achievements.
Do not inflate seniority or add unsupported ATS keywords.
Do not turn training or developing knowledge into professional experience.
Do not claim protected structural gaps as existing strengths."""


def build_tailored_cv_generation_request(
    context: ApplicationContext,
) -> TailoredCVGenerationRequest:
    selected = {}
    for group in (
        context.direct_evidence,
        context.transferable_evidence,
        context.supporting_evidence,
        context.developing_evidence,
    ):
        for item in group:
            selected.setdefault(item.evidence_ref, item)

    payload = {
        "candidate_id": context.candidate_id,
        "job_id": context.job_id,
        "application_context_signature": context.source_signature,
        "job": {
            "title": context.job_title,
            "company": context.company,
            "role_family": context.role_family,
            "level": context.job_level,
            "core_requirements": list(context.core_requirements),
        },
        "selected_evidence": [asdict(selected[key]) for key in sorted(selected)],
        "positioning_themes": [asdict(item) for item in context.positioning_themes],
        "development_gaps": list(context.development_gaps),
        "protected_structural_gaps": list(context.structural_gaps),
        "allowed_claim_types": list(ALLOWED_CLAIM_TYPES),
        "output_schema_version": "tailored-cv-v1",
    }
    prompt = _INSTRUCTIONS + "\n\nGENERATION_INPUT:\n" + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    signature = build_source_signature(
        {
            "schema_version": "tailored-cv-generation-request-v1",
            "instructions": _INSTRUCTIONS,
            "payload": payload,
        }
    )

    return TailoredCVGenerationRequest(
        candidate_id=context.candidate_id,
        job_id=context.job_id,
        application_context_signature=context.source_signature,
        job_title=context.job_title,
        company=context.company,
        role_family=context.role_family,
        job_level=context.job_level,
        core_requirements=list(context.core_requirements),
        selected_evidence=payload["selected_evidence"],
        development_gaps=list(context.development_gaps),
        protected_structural_gaps=list(context.structural_gaps),
        allowed_claim_types=list(ALLOWED_CLAIM_TYPES),
        prompt=prompt,
        source_signature=signature,
    )
