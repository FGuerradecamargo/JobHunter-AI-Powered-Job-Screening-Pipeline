from dataclasses import asdict

from models.application_context import ApplicationContext
from models.tailored_cv_contract import TailoredCVGenerationRequest


ALLOWED_CLAIM_TYPES = (
    "professional_experience",
    "transferable_capability",
    "skill",
    "developing_knowledge",
    "summary",
)


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

    return TailoredCVGenerationRequest(
        candidate_id=context.candidate_id,
        job_id=context.job_id,
        application_context_signature=context.source_signature,
        job_title=context.job_title,
        company=context.company,
        role_family=context.role_family,
        job_level=context.job_level,
        core_requirements=list(context.core_requirements),
        selected_evidence=[
            asdict(selected[key])
            for key in sorted(selected)
        ],
        development_gaps=list(context.development_gaps),
        protected_structural_gaps=list(context.structural_gaps),
        allowed_claim_types=list(ALLOWED_CLAIM_TYPES),
    )

