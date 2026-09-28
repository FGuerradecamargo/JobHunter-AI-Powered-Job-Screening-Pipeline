from __future__ import annotations

from dataclasses import asdict
import re

from models.application_contract import ApplicationEvidenceRef
from models.application_context import PositioningTheme
from models.interview_prep_contract import InterviewPrepContract

from services.application_contract_repository import (
    ApplicationContractSourceRepository,
)
from services.candidate_onboarding_repository import (
    CandidateOnboardingRepository,
)
from services.candidate_profile_source import (
    load_confirmed_candidate_profile_input,
)
from services.career_memory_source_builder import (
    build_source_signature,
)
from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.profile_snapshot_repository import (
    ProfileSnapshotRepository,
)
from services.role_family_normalizer import (
    normalize_role_family,
)


_ACTIVE_INTERVIEW_STAGES = {
    "interview",
    "final_interview",
}


def _text(value) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    )


def _strings(values) -> list[str]:
    if not isinstance(
        values,
        (list, tuple, set),
    ):
        return []

    result = {
        _text(value)
        for value in values
        if _text(value)
    }

    return sorted(
        result,
        key=str.casefold,
    )


def _source_id(
    evidence_ref: str,
    prefix: str,
) -> str:
    value = str(evidence_ref or "")

    if not value.startswith(prefix):
        return ""

    remainder = value[len(prefix):]

    return remainder.split(":", 1)[0].strip()


def build_legacy_active_interview_prep_contract(
    candidate_id: str,
    job_id: str,
    *,
    interview_stage: str,
    application_final_status: str = "",
    source_repository=None,
    onboarding_repository=None,
    career_update_repository=None,
    snapshot_repository=None,
    profile_input_loader=None,
) -> InterviewPrepContract:
    """
    Compatibility boundary for an already-active interview whose persisted
    opportunity analysis predates HiringCase.

    This does NOT make the historical opportunity application-eligible.
    It authorizes interview preparation only from:
      - the existing active interview state,
      - persisted legacy job-analysis requirements/gaps, and
      - confirmed candidate source records.

    A source containing a current `hiring_case` key is never treated as
    legacy. Invalid current data must continue to fail closed.
    """
    candidate_id = _text(candidate_id)
    job_id = _text(job_id)
    stage = _text(interview_stage).casefold()
    final_status = _text(
        application_final_status
    ).casefold()

    if not candidate_id or not job_id:
        raise ValueError(
            "Candidate and job are required."
        )

    if (
        final_status
        or stage not in _ACTIVE_INTERVIEW_STAGES
    ):
        raise ValueError(
            "An active interview stage is required."
        )

    source_repository = (
        source_repository
        or ApplicationContractSourceRepository()
    )

    source = source_repository.get_analysis_source(
        candidate_id,
        job_id,
    )

    if source is None:
        raise ValueError(
            "Legacy interview analysis source was not found."
        )

    if (
        source.candidate_id != candidate_id
        or source.job_id != job_id
    ):
        raise PermissionError(
            "Legacy interview source belongs to another scope."
        )

    analysis = (
        source.analysis
        if isinstance(source.analysis, dict)
        else {}
    )

    # Critical fail-closed rule:
    # a malformed CURRENT HiringCase is not legacy data.
    if "hiring_case" in analysis:
        raise ValueError(
            "Current HiringCase data cannot use legacy compatibility."
        )

    requirements = _strings(
        analysis.get(
            "core_requirements",
            [],
        )
    )

    development_gaps = _strings(
        analysis.get(
            "development_gaps",
            [],
        )
    )

    structural_gaps = _strings(
        [
            *_strings(
                analysis.get(
                    "structural_gaps",
                    [],
                )
            ),
            *_strings(
                analysis.get(
                    "hard_conflicts",
                    [],
                )
            ),
        ]
    )

    if not (
        requirements
        or development_gaps
        or structural_gaps
    ):
        raise ValueError(
            "Legacy interview source has no preparation material."
        )

    loader = (
        profile_input_loader
        or load_confirmed_candidate_profile_input
    )

    if profile_input_loader is None:
        onboarding_repository = (
            onboarding_repository
            or CandidateOnboardingRepository()
        )

        career_update_repository = (
            career_update_repository
            or CareerUpdateRepository()
        )

    source_snapshot, source_evidence = loader(
        candidate_id,
        onboarding_repository,
        career_update_repository,
    )

    if source_snapshot.candidate_id != candidate_id:
        raise PermissionError(
            "Candidate source snapshot belongs to another candidate."
        )

    experience_by_id = {
        str(item.get("experience_id") or ""): item
        for item in source_snapshot.payload.get(
            "experiences",
            [],
        )
        if isinstance(item, dict)
        and item.get("experience_id")
    }

    authorized_evidence = []

    for evidence in source_evidence:
        statement = _text(
            getattr(
                evidence,
                "summary",
                "",
            )
        )

        if not statement:
            continue

        if evidence.source_type == "professional_experience":
            source_id = _source_id(
                evidence.ref,
                "professional_experience:",
            )

            if not source_id:
                continue

            experience = experience_by_id.get(
                source_id,
                {},
            )

            authorized_evidence.append(
                ApplicationEvidenceRef(
                    evidence_ref=evidence.ref,
                    source_type="professional_experience",
                    source_id=source_id,
                    authority="professional_fact",
                    statement=statement,
                    metadata={
                        "company": _text(
                            experience.get(
                                "company",
                                "",
                            )
                        ),
                        "start_date": _text(
                            experience.get(
                                "start_date",
                                "",
                            )
                        ),
                        "end_date": _text(
                            experience.get(
                                "end_date",
                                "",
                            )
                        ),
                        "source_authority": (
                            "confirmed_user_record"
                        ),
                    },
                )
            )

        elif evidence.source_type == "career_update":
            source_id = _source_id(
                evidence.ref,
                "career_update:",
            )

            if not source_id:
                continue

            authorized_evidence.append(
                ApplicationEvidenceRef(
                    evidence_ref=evidence.ref,
                    source_type="career_update",
                    source_id=source_id,
                    authority="candidate_update",
                    statement=statement,
                    metadata={
                        "source_authority": (
                            "confirmed_user_record"
                        ),
                    },
                )
            )

    authorized_evidence.sort(
        key=lambda item: item.evidence_ref
    )

    # Optional, conservative capability linkage:
    # only exact labels already selected by the historical analysis
    # can become positioning themes. No fuzzy matching.
    selector_values = [
        *_strings(
            analysis.get(
                "requirements_met",
                [],
            )
        ),
        *_strings(
            analysis.get(
                "strengths",
                [],
            )
        ),
    ]

    selector_keys = {
        _text(value).casefold()
        for value in selector_values
        if _text(value)
    }

    positioning_themes = []

    snapshot_repository = (
        snapshot_repository
        or ProfileSnapshotRepository()
    )

    candidate_profile = (
        snapshot_repository.current_candidate(
            candidate_id
        )
    )

    if (
        candidate_profile is not None
        and candidate_profile.candidate_id
        == candidate_id
        and candidate_profile.memory_signature
        == source_snapshot.source_signature
    ):
        available_refs = {
            item.evidence_ref
            for item in authorized_evidence
        }

        for capability in candidate_profile.capabilities:
            label = _text(
                capability.label
            )

            refs = sorted(
                set(capability.evidence_refs)
                & available_refs
            )

            if (
                label
                and refs
                and label.casefold()
                in selector_keys
            ):
                positioning_themes.append(
                    PositioningTheme(
                        theme=label,
                        evidence_refs=refs,
                    )
                )

    positioning_themes.sort(
        key=lambda item: item.theme.casefold()
    )

    market_signal = analysis.get(
        "market_signal",
        {},
    )

    if not isinstance(
        market_signal,
        dict,
    ):
        market_signal = {}

    role_family = normalize_role_family(
        market_signal.get(
            "role_family",
            "",
        )
    )

    compatibility_payload = {
        "authority": (
            "legacy-active-interview-compatibility"
        ),
        "candidate_id": candidate_id,
        "job_id": job_id,
        "analysis_id": source.analysis_id,
        "interview_stage": stage,
        "source_recommendation": (
            source.recommendation
        ),
        "job": {
            "title": source.job.get(
                "title",
                "",
            ),
            "company": source.job.get(
                "company",
                "",
            ),
        },
        "requirements": requirements,
        "development_gaps": development_gaps,
        "structural_gaps": structural_gaps,
        "authorized_evidence": [
            asdict(item)
            for item in authorized_evidence
        ],
        "positioning_themes": [
            asdict(item)
            for item in positioning_themes
        ],
        "candidate_source_signature": (
            source_snapshot.source_signature
        ),
    }

    compatibility_signature = (
        build_source_signature(
            compatibility_payload
        )
    )

    return InterviewPrepContract(
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_id=source.analysis_id,
        application_context_signature=(
            "legacy-active-interview:"
            + compatibility_signature
        ),
        interview_stage=stage,
        application_final_status="",
        eligible=True,
        job_title=_text(
            source.job.get(
                "title",
                "",
            )
        ),
        company=_text(
            source.job.get(
                "company",
                "",
            )
        ),
        role_family=role_family,
        job_level=_text(
            analysis.get(
                "job_level",
                "",
            )
        ),
        authorized_evidence=authorized_evidence,
        development_gaps=development_gaps,
        protected_structural_gaps=structural_gaps,
        target_requirements=requirements,
        positioning_themes=positioning_themes,
        source_signature=compatibility_signature,
    )
