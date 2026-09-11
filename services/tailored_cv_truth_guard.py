from __future__ import annotations

from dataclasses import asdict, replace
import re

from models.application_context import ApplicationContext
from models.tailored_cv_contract import (
    CVValidationIssue,
    CVValidationResult,
    DraftTailoredCV,
    DraftTailoredCVExperience,
    TailoredCVStatement,
)
from services.career_memory_source_builder import build_source_signature
from services.tailored_cv_generation_request_builder import ALLOWED_CLAIM_TYPES


_AUTHORITY_BY_CLAIM_TYPE = {
    "professional_experience": {"professional_fact"},
    "transferable_capability": {
        "professional_fact",
        "transferable_evidence",
    },
    "skill": {
        "professional_fact",
        "candidate_profile_fact",
    },
    "developing_knowledge": {
        "developing_evidence",
        "candidate_update",
    },
    "summary": {
        "professional_fact",
        "transferable_evidence",
        "candidate_profile_fact",
        "candidate_update",
        "developing_evidence",
    },
}


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _protected_claim_terms(value: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9]+", _normalize(value).casefold()))
    ownership_forms = {"own", "owned", "owner", "owners", "owning", "ownership"}
    if terms & ownership_forms:
        terms.difference_update(ownership_forms)
        terms.add("own")
    return terms


def _issue(code: str, location: str, message: str) -> CVValidationIssue:
    return CVValidationIssue(code=code, location=location, message=message)


def _normalize_statement(statement: TailoredCVStatement) -> TailoredCVStatement:
    return replace(
        statement,
        text=_normalize(statement.text),
        claim_type=_normalize(statement.claim_type),
        evidence_refs=sorted(
            {_normalize(ref) for ref in statement.evidence_refs if _normalize(ref)}
        ),
    )


def _all_statement_locations(draft: DraftTailoredCV):
    yield "headline", draft.headline, None
    for index, item in enumerate(draft.professional_summary):
        yield f"professional_summary[{index}]", item, None
    for index, item in enumerate(draft.key_skills):
        yield f"key_skills[{index}]", item, None
    for experience_index, experience in enumerate(draft.experiences):
        for bullet_index, item in enumerate(experience.bullets):
            yield (
                f"experiences[{experience_index}].bullets[{bullet_index}]",
                item,
                experience.source_experience_id,
            )
    for index, item in enumerate(draft.additional_relevant_information):
        yield f"additional_relevant_information[{index}]", item, None


def _normalized_draft(draft: DraftTailoredCV) -> DraftTailoredCV:
    experiences = [
        replace(
            experience,
            source_experience_id=_normalize(experience.source_experience_id),
            company=_normalize(experience.company),
            role=_normalize(experience.role),
            bullets=[_normalize_statement(item) for item in experience.bullets],
        )
        for experience in draft.experiences
    ]
    return replace(
        draft,
        candidate_id=_normalize(draft.candidate_id),
        job_id=_normalize(draft.job_id),
        application_context_signature=_normalize(
            draft.application_context_signature
        ),
        headline=_normalize_statement(draft.headline),
        professional_summary=[
            _normalize_statement(item) for item in draft.professional_summary
        ],
        key_skills=[_normalize_statement(item) for item in draft.key_skills],
        experiences=experiences,
        additional_relevant_information=[
            _normalize_statement(item)
            for item in draft.additional_relevant_information
        ],
    )


def validate_tailored_cv_draft(
    draft: DraftTailoredCV,
    context: ApplicationContext,
) -> CVValidationResult:
    normalized = _normalized_draft(draft)
    issues = []

    if normalized.candidate_id != context.candidate_id:
        issues.append(_issue("candidate_mismatch", "candidate_id", "Wrong candidate."))
    if normalized.job_id != context.job_id:
        issues.append(_issue("job_mismatch", "job_id", "Wrong job."))
    if normalized.application_context_signature != context.source_signature:
        issues.append(
            _issue(
                "context_signature_mismatch",
                "application_context_signature",
                "Application Context signature does not match.",
            )
        )

    authorized = {
        item.evidence_ref: item for item in context.available_evidence
    }
    structural_gaps = sorted(
        {_normalize(item) for item in context.structural_gaps if _normalize(item)},
        key=str.casefold,
    )

    for location, statement, experience_id in _all_statement_locations(normalized):
        if not statement.text:
            issues.append(_issue("empty_statement", location, "Statement is empty."))
            continue
        if statement.claim_type not in ALLOWED_CLAIM_TYPES:
            issues.append(
                _issue("invalid_claim_type", location, "Claim type is not allowed.")
            )
        if not statement.evidence_refs:
            issues.append(
                _issue("missing_evidence_ref", location, "Statement has no evidence.")
            )
            continue

        known = []
        for reference in statement.evidence_refs:
            item = authorized.get(reference)
            if item is None:
                issues.append(
                    _issue(
                        "unknown_evidence_ref",
                        location,
                        f"Evidence reference is not authorized: {reference}",
                    )
                )
            else:
                known.append(item)

        allowed = _AUTHORITY_BY_CLAIM_TYPE.get(statement.claim_type, set())
        unsupported_authorities = {
            item.authority for item in known if item.authority not in allowed
        }
        if unsupported_authorities:
            code = "insufficient_evidence_authority"
            if "developing_evidence" in unsupported_authorities:
                code = "developing_evidence_overclaim"
            elif "transferable_evidence" in unsupported_authorities:
                code = "transferable_evidence_overclaim"
            issues.append(
                _issue(
                    code,
                    location,
                    "Evidence authority cannot support claim type.",
                )
            )

        if experience_id is not None:
            experience_evidence = [
                item for item in known if item.source_type == "professional_experience"
            ]
            if not experience_evidence or any(
                item.source_id != experience_id for item in experience_evidence
            ) or any(item.source_type != "professional_experience" for item in known):
                issues.append(
                    _issue(
                        "experience_source_mismatch",
                        location,
                        "Experience bullet evidence does not match its source experience.",
                    )
                )

        statement_terms = _protected_claim_terms(statement.text)
        for gap in structural_gaps:
            gap_terms = _protected_claim_terms(gap)
            if not gap_terms or not gap_terms.issubset(statement_terms):
                continue
            supported = any(
                item.authority == "professional_fact"
                and gap_terms.issubset(_protected_claim_terms(item.statement))
                for item in known
            )
            if not supported:
                issues.append(
                    _issue(
                        "protected_gap_conflict",
                        location,
                        "Statement explicitly conflicts with a protected structural gap.",
                    )
                )

    draft_signature = build_source_signature(
        {
            "application_context_signature": context.source_signature,
            "draft": asdict(normalized),
        }
    )
    return CVValidationResult(
        valid=not issues,
        issues=issues,
        normalized_draft=normalized,
        draft_signature=draft_signature,
        protected_structural_gaps=structural_gaps,
    )
