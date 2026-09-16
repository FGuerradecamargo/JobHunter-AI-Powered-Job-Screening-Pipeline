"""Conservative exact-label adapter. No NLP, IO, scoring or LLM inference."""

import hashlib

from models.hiring_case import (
    HiringCaseInput,
    OpportunitySignal,
    OpportunitySignalKind,
    OpportunitySignalState,
    RequirementAssessment,
    RequirementEvidenceState,
    RequirementImportance,
)
from models.hiring_case_shadow import HiringCaseShadowSource, ShadowUnavailableReason
from services.application_contract_builder import build_application_evidence
from services.role_family_normalizer import role_family_key


class ShadowInputUnavailable(ValueError):
    def __init__(self, reason: ShadowUnavailableReason):
        self.reason = reason
        super().__init__(reason.value)


def _text(value) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _key(value) -> str:
    return _text(value).casefold().rstrip(".;:,")


def _labels(values) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    return sorted({_text(value) for value in values if _key(value)})


def _check_scope(source: HiringCaseShadowSource) -> None:
    candidate = source.candidate
    analysis = source.analysis_source
    if not candidate.id or not analysis.job_id or candidate.id != analysis.candidate_id:
        raise PermissionError("Shadow candidate scope is invalid.")
    if analysis.job.get("id") != analysis.job_id:
        raise PermissionError("Shadow job scope is invalid.")
    if source.job_profile is not None and source.job_profile.job_id != analysis.job_id:
        raise PermissionError("Shadow profile scope is invalid.")
    if source.objective is not None and source.objective.candidate_id != candidate.id:
        raise PermissionError("Shadow objective scope is invalid.")
    if any(update.candidate_id != candidate.id for update in source.career_updates):
        raise PermissionError("Shadow career update scope is invalid.")
    if any(
        gap.candidate_id != candidate.id or gap.job_id != analysis.job_id
        for gap in source.confirmed_gaps
    ):
        raise PermissionError("Shadow gap confirmation scope is invalid.")


def _requirements(source, *, blocked=False):
    profile = source.job_profile
    core = []
    important = []
    nice = []
    if profile is not None:
        core = [
            *_labels(profile.must_have_capabilities),
            *_labels(profile.must_have_experience),
            *_labels(profile.required_qualifications),
            *_labels(profile.structural_requirements),
        ]
        important = [
            *_labels(profile.key_responsibilities),
            *_labels(profile.tools_and_technologies),
        ]
        nice = _labels(profile.nice_to_have)
    if not core:
        core = _labels(source.analysis_source.analysis.get("core_requirements"))
    if not core and not blocked:
        # The v1 engine considers an empty core list strong. Abstain at this boundary.
        raise ShadowInputUnavailable(ShadowUnavailableReason.CORE_REQUIREMENTS_MISSING)
    selected = {}
    for importance, labels in (
        (RequirementImportance.CORE, core),
        (RequirementImportance.IMPORTANT, important),
        (RequirementImportance.NICE_TO_HAVE, nice),
    ):
        for label in sorted(labels):
            selected.setdefault(_key(label), (label, importance))
    return {key: selected[key] for key in sorted(selected)}


def _gap_keys(source, requirements):
    updates = {item.id: item for item in source.career_updates if item.id}
    confirmed = set()
    for gap in source.confirmed_gaps:
        update = updates.get(gap.source_update_id)
        key = _key(gap.requirement)
        if update is None or not _text(update.description) or key not in requirements:
            raise ValueError("Gap confirmation requires an existing source and requirement.")
        confirmed.add(key)
    return confirmed


def _assess_requirement(key, label, importance, evidence, gap_keys, experience_ids):
    matches = [item for item in evidence if _key(item.statement) == key]
    direct = [
        item for item in matches
        if item.source_type == "professional_experience"
        and item.source_id in experience_ids
        and item.metadata.get("evidence_kind") != "transferable_capability"
        and item.authority == "professional_fact"
    ]
    transferable = [
        item for item in matches
        if item.authority == "transferable_evidence"
        or (
            item.source_type == "professional_experience"
            and item.source_id in experience_ids
            and item.metadata.get("evidence_kind") == "transferable_capability"
        )
    ]
    state = RequirementEvidenceState.EVIDENCE_MISSING
    refs = []
    defensible = False
    rationale = "No exact, source-backed proof is available; capability is unknown."
    if key in gap_keys and (direct or transferable):
        rationale = "Source evidence conflicts with a confirmed gap; review is needed."
    elif key in gap_keys:
        state = RequirementEvidenceState.GAP
        rationale = "Insufficient capability was explicitly confirmed against an existing source."
    elif direct:
        state = RequirementEvidenceState.PROVEN
        refs = [item.evidence_ref for item in direct]
        defensible = True
        rationale = "An exact requirement label is supported by recorded professional experience."
    elif transferable:
        state = RequirementEvidenceState.TRANSFERABLE
        refs = [item.evidence_ref for item in transferable]
        defensible = any(item.source_type == "professional_experience" for item in transferable)
        rationale = "Recorded transferable capability supports a bridge, not direct proof."
    return RequirementAssessment(
        requirement_id="requirement_" + hashlib.sha256(key.encode("utf-8")).hexdigest(),
        requirement=label,
        importance=importance,
        evidence_state=state,
        evidence_refs=refs,
        rationale=rationale,
        interview_defensible=defensible,
    )


def _opportunity_signals(source):
    # Emit every dimension so omitted information also lowers confidence.
    signals = {
        kind: OpportunitySignal(
            kind=kind, state=OpportunitySignalState.UNKNOWN,
            importance=RequirementImportance.IMPORTANT,
            rationale="Comparable source facts or explicit preferences are unavailable.",
        )
        for kind in OpportunitySignalKind
    }

    def set_signal(kind, state, importance, rationale):
        signals[kind] = OpportunitySignal(kind, state, importance, rationale)

    profile = source.job_profile
    candidate = source.candidate
    objective = source.objective
    families = (
        objective.desired_role_families
        if objective is not None and objective.active and objective.desired_role_families
        else candidate.target_role_families
    )
    if profile is not None:
        family = role_family_key(profile.role_family)
        if family and family in {role_family_key(item) for item in _labels(families)}:
            set_signal(
                OpportunitySignalKind.CAREER_DIRECTION, OpportunitySignalState.POSITIVE,
                RequirementImportance.CORE, "Role family matches the recorded career direction.",
            )
        elif not (objective is not None and objective.active and objective.desired_role_families) and (
            _key(profile.canonical_role) in {_key(item) for item in _labels(candidate.target_roles)}
        ):
            set_signal(
                OpportunitySignalKind.CAREER_DIRECTION, OpportunitySignalState.POSITIVE,
                RequirementImportance.CORE, "Canonical role matches a recorded target role.",
            )

        content = {_key(item) for item in _labels(profile.key_responsibilities)}
        matches = [item for item in candidate.priorities if item.active and _key(item.text) in content]
        if any(item.direction == "negative" for item in matches):
            set_signal(
                OpportunitySignalKind.ROLE_CONTENT, OpportunitySignalState.NEGATIVE,
                RequirementImportance.CORE, "Role content conflicts with an explicit active priority.",
            )
        elif any(item.direction == "positive" for item in matches):
            set_signal(
                OpportunitySignalKind.ROLE_CONTENT, OpportunitySignalState.POSITIVE,
                RequirementImportance.IMPORTANT, "Role content matches an explicit active priority.",
            )

    modes = {
        _key(value) for value in _labels(profile.work_conditions if profile else [])
    } & {"remote", "hybrid", "onsite"}
    if source.analysis_source.job.get("remote") is True:
        modes.add("remote")
    if len(modes) == 1:
        mode = next(iter(modes))
        if getattr(candidate.preferences, mode + "_allowed") is False:
            set_signal(
                OpportunitySignalKind.WORK_MODE_LOCATION, OpportunitySignalState.NEGATIVE,
                RequirementImportance.IMPORTANT, "Known work mode conflicts with a recorded preference.",
            )
    # Salary strings have no shared currency/period contract. Allowed work modes
    # are compatible, but permission alone is not evidence of high personal value.
    return list(signals.values())


def build_hiring_case_input(source: HiringCaseShadowSource) -> HiringCaseInput:
    _check_scope(source)
    analysis = source.analysis_source
    if not _text(analysis.analysis_id) or not isinstance(analysis.analysis, dict) or not analysis.analysis:
        raise ShadowInputUnavailable(ShadowUnavailableReason.ANALYSIS_MISSING)
    blocked = bool(_labels(analysis.analysis.get("hard_conflicts"))) or (
        analysis.analysis.get("rule_rejection_type") == "hard_filter"
    )
    labels = _requirements(source, blocked=blocked)
    gap_keys = _gap_keys(source, labels)
    evidence = build_application_evidence(source.candidate, list(source.career_updates))
    experience_ids = {
        item.source_experience_id for item in source.candidate.professional_experiences
        if _text(item.source_experience_id)
    }
    requirements = [
        _assess_requirement(key, label, importance, evidence, gap_keys, experience_ids)
        for key, (label, importance) in labels.items()
    ]
    return HiringCaseInput(
        candidate_id=source.candidate.id, job_id=analysis.job_id,
        requirements=requirements, opportunity_signals=_opportunity_signals(source),
        hard_eligibility_blockers=["Existing eligibility blocker"] if blocked else [],
        # Existing level_assessment is prose, not a verified mismatch flag.
        seniority_context_mismatch=False,
    )
