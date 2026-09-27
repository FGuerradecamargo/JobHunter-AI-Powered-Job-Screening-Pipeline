from __future__ import annotations

from dataclasses import asdict
import hashlib
import re

from models.application_contract import (
    ApplicationAnalysisSource,
    ApplicationContract,
    ApplicationEvidenceRef,
)
from models.candidate import Candidate
from models.career_update import CareerUpdate
from services.career_memory_source_builder import build_source_signature


APPLICATION_CONTRACT_SCHEMA_VERSION = "application-contract-v1"
APPLICATION_ELIGIBLE_RECOMMENDATIONS = {
    "best_match",
    "potential",
    "good_opportunity",
}


def build_official_application_contract(*, candidate_profile, job_profile, hiring_case,
                                        source_snapshot, source_evidence, analysis_source):
    if not (candidate_profile.candidate_id == hiring_case.candidate_id == analysis_source.candidate_id
            == source_snapshot.candidate_id and job_profile.job_id == hiring_case.job_id == analysis_source.job_id):
        raise PermissionError("Application sources belong to different relationships.")
    if (candidate_profile.memory_signature != source_snapshot.source_signature
            or hiring_case.candidate_signature != candidate_profile.memory_signature
            or hiring_case.job_signature != job_profile.job_signature
            or hiring_case.candidate_profile_version != candidate_profile.profile_version
            or hiring_case.job_profile_version != job_profile.profile_version):
        raise ValueError("Application sources require reanalysis.")
    experiences = {str(item["experience_id"]): item for item in source_snapshot.payload.get("experiences", [])}
    evidence = []
    for source in source_evidence:
        if source.ref not in candidate_profile.source_refs or source.source_type not in {"professional_experience", "career_update"}:
            continue
        source_id = (next((key for key in experiences if source.ref.startswith(f"professional_experience:{key}:")), "")
                     if source.source_type == "professional_experience" else source.ref.removeprefix("career_update:"))
        if not source_id:
            raise ValueError("Application evidence has no confirmed source identity.")
        experience = experiences.get(source_id, {})
        evidence.append(ApplicationEvidenceRef(
            evidence_ref=source.ref, source_type=source.source_type, source_id=source_id,
            authority="professional_fact" if source.source_type == "professional_experience" else "candidate_update",
            statement=source.summary,
            metadata={"company": experience.get("company", ""), "stated_role": "",
                      "start_date": experience.get("start_date", ""), "end_date": experience.get("end_date"),
                      "source_authority": "confirmed_user_record"},
        ))
    from services.hiring_case_compatibility import hiring_case_analysis
    analysis = hiring_case_analysis(hiring_case)
    return ApplicationContract(
        candidate_id=hiring_case.candidate_id, job_id=hiring_case.job_id,
        analysis_id=analysis_source.analysis_id, recommendation=analysis["recommendation"],
        eligible=hiring_case.surfaced and not hiring_case.hard_eligibility_blockers,
        evidence_refs=evidence, development_gaps=analysis["development_gaps"],
        structural_gaps=analysis["hard_conflicts"],
        source_signature=build_source_signature({"candidate": asdict(candidate_profile), "job": asdict(job_profile),
            "case": asdict(hiring_case), "sources": [asdict(item) for item in evidence],
            "analysis_id": analysis_source.analysis_id}),
    )


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _strings(values) -> list[str]:
    result = {_normalize(value) for value in values or [] if _normalize(value)}
    return sorted(result, key=str.casefold)


def _evidence_ref(source_type: str, source_id: str, statement: str) -> str:
    canonical = "|".join(
        (source_type.casefold(), source_id.casefold(), statement.casefold())
    )
    return "application_evidence_" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _add_evidence(
    target: dict[str, ApplicationEvidenceRef],
    *,
    source_type: str,
    source_id: str,
    authority: str,
    statement,
    metadata=None,
) -> None:
    normalized_statement = _normalize(statement)
    normalized_source_id = _normalize(source_id)
    if not normalized_statement or not normalized_source_id:
        return
    reference = _evidence_ref(
        source_type,
        normalized_source_id,
        normalized_statement,
    )
    target.setdefault(
        reference,
        ApplicationEvidenceRef(
            evidence_ref=reference,
            source_type=source_type,
            source_id=normalized_source_id,
            authority=authority,
            statement=normalized_statement,
            metadata=dict(metadata or {}),
        ),
    )


def _experience_source_id(experience) -> str:
    if _normalize(experience.source_experience_id):
        return _normalize(experience.source_experience_id)
    payload = asdict(experience)
    return "derived-" + build_source_signature(payload)[:24]


def build_application_evidence(
    candidate: Candidate,
    career_updates: list[CareerUpdate],
) -> list[ApplicationEvidenceRef]:
    evidence = {}

    for experience in candidate.professional_experiences or []:
        source_id = _experience_source_id(experience)
        base_metadata = {
            "company": _normalize(experience.company),
            "stated_role": _normalize(experience.stated_role),
        }
        for field_name, values in (
            ("summary", [experience.summary]),
            ("responsibility", experience.responsibilities),
            ("demonstrated_capability", experience.demonstrated_capabilities),
            ("transferable_capability", experience.transferable_capabilities),
            ("tool", experience.tools),
            ("domain", experience.domains),
            ("supporting_evidence", experience.evidence),
        ):
            for statement in values or []:
                _add_evidence(
                    evidence,
                    source_type="professional_experience",
                    source_id=source_id,
                    authority="professional_fact",
                    statement=statement,
                    metadata={**base_metadata, "evidence_kind": field_name},
                )

    for field_name, source_type, authority in (
        ("proven_capabilities", "proven_capability", "professional_fact"),
        (
            "transferable_capabilities",
            "transferable_capability",
            "transferable_evidence",
        ),
        (
            "developing_capabilities",
            "developing_capability",
            "developing_evidence",
        ),
        ("skills", "skill", "candidate_profile_fact"),
        ("technical_tools", "technical_tool", "candidate_profile_fact"),
        ("domain_experience", "domain_evidence", "candidate_profile_fact"),
    ):
        for statement in getattr(candidate, field_name, []) or []:
            _add_evidence(
                evidence,
                source_type=source_type,
                source_id=f"candidate:{candidate.id}:{field_name}",
                authority=authority,
                statement=statement,
            )

    for update in career_updates or []:
        if update.candidate_id != candidate.id:
            raise PermissionError("Career update belongs to another candidate.")
        _add_evidence(
            evidence,
            source_type="career_update",
            source_id=update.id,
            authority="candidate_update",
            statement=update.description,
            metadata={"update_type": _normalize(update.update_type)},
        )

    return sorted(evidence.values(), key=lambda item: item.evidence_ref)


def _order_insensitive(value):
    if isinstance(value, dict):
        return {
            str(key): _order_insensitive(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set)):
        items = [_order_insensitive(item) for item in value]
        return sorted(items, key=lambda item: build_source_signature({"item": item}))
    if isinstance(value, str):
        return _normalize(value)
    return value


def build_application_contract(
    *,
    candidate: Candidate,
    career_updates: list[CareerUpdate],
    analysis_source: ApplicationAnalysisSource,
) -> ApplicationContract:
    if analysis_source.candidate_id != candidate.id:
        raise PermissionError("Candidate-job analysis belongs to another candidate.")
    if _normalize(analysis_source.job_id) != _normalize(
        analysis_source.job.get("id")
    ):
        raise PermissionError("Candidate-job analysis does not own this job.")

    evidence_refs = build_application_evidence(candidate, career_updates)
    recommendation = _normalize(analysis_source.recommendation)
    development_gaps = _strings(
        analysis_source.analysis.get("development_gaps", [])
    )
    structural_gaps = _strings(
        analysis_source.analysis.get("structural_gaps", [])
    )
    signature_payload = {
        "candidate_id": candidate.id,
        "job": _order_insensitive(analysis_source.job),
        "analysis_id": analysis_source.analysis_id,
        "recommendation": recommendation,
        "analysis": _order_insensitive(analysis_source.analysis),
        "evidence_refs": [asdict(item) for item in evidence_refs],
    }

    return ApplicationContract(
        candidate_id=candidate.id,
        job_id=analysis_source.job_id,
        analysis_id=analysis_source.analysis_id,
        recommendation=recommendation,
        eligible=recommendation in APPLICATION_ELIGIBLE_RECOMMENDATIONS,
        evidence_refs=evidence_refs,
        development_gaps=development_gaps,
        structural_gaps=structural_gaps,
        source_signature=build_source_signature(signature_payload),
        schema_version=APPLICATION_CONTRACT_SCHEMA_VERSION,
    )

