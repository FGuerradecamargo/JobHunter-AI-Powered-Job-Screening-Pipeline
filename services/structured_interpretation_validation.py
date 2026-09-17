"""Structural and authority checks only; this module does not infer semantic matches."""
from dataclasses import fields, is_dataclass, replace
from enum import Enum
from types import UnionType
from typing import get_args, get_origin, get_type_hints
from services.job_evidence_constraints import validate_evidence_requirement
from services.temporal_applicability import validate_temporal_requirement, resolve_temporal_applicability
from models.profile_interpretation import TemporalEvidenceMetadata
from models.hiring_case import TemporalApplicability

from models.hiring_case import OpportunitySignalKind as Kind, OpportunitySignalState as SignalState, RequirementEvidenceState as Evidence, RequirementImportance
from models.profile_interpretation import CandidateProfileDraft, JobProfileDraft, InterpretationAuthority as Authority
from models.structured_interpretation import (
    FactState, InterpretationOperation as Operation, LinkConfidence, LinkReason,
    OpportunityInterpretation, InterpretedOpportunitySignal, SemanticLinks,
    SourceRefClass as RefClass, ValidationIssue as Issue,
)


class InterpretationValidationError(ValueError):
    def __init__(self, code: Issue):
        self.code = code
        super().__init__(code.value)


def fail(code):
    raise InterpretationValidationError(code)


def decode_structure(value, annotation):
    """Strict JSON-to-dataclass decoding: no coercion, extras or private error echo."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is UnionType:
        for member in args:
            try:
                return decode_structure(value, member)
            except (InterpretationValidationError, ValueError, TypeError):
                pass
        fail(Issue.INVALID_SCHEMA)
    if annotation is type(None):
        if value is not None:
            fail(Issue.INVALID_SCHEMA)
        return None
    if origin is tuple:
        if not isinstance(value, (list, tuple)) or len(args) != 2 or args[1] is not Ellipsis:
            fail(Issue.INVALID_SCHEMA)
        return tuple(decode_structure(item, args[0]) for item in value)
    if is_dataclass(annotation):
        if type(value) is not dict:
            fail(Issue.INVALID_SCHEMA)
        names = {item.name for item in fields(annotation)}
        if set(value) - names:
            fail(Issue.INVALID_SCHEMA)
        hints = get_type_hints(annotation)
        try:
            return annotation(**{key: decode_structure(item, hints[key]) for key, item in value.items()})
        except (TypeError, ValueError):
            fail(Issue.INVALID_SCHEMA)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if not isinstance(value, str):
            fail(Issue.INVALID_SCHEMA)
        try:
            return annotation(value)
        except ValueError:
            fail(Issue.INVALID_SCHEMA)
    if type(value) is not annotation:
        fail(Issue.INVALID_SCHEMA)
    return value


def unique(items):
    if len(items) != len(set(items)) or any(not item.strip() for item in items):
        fail(Issue.INVALID_SCHEMA)


class SourceRefRegistry:
    """Constructed from trusted input sources, never from an interpreter response."""
    _candidate_types = {
        "professional_experience", "career_update", "career_objective",
        "candidate_preference", "candidate_context",
    }

    def __init__(self, request):
        unique([item.ref for item in request.source_registry])
        self.entries = {item.ref: item for item in request.source_registry}
        for item in self.entries.values():
            if not isinstance(item.source_class, RefClass):
                fail(Issue.INVALID_SCHEMA)
            derived = item.source_type in {"checkpoint", "derived_checkpoint", "inference", "hypothesis", "continuity", "candidate_profile"}
            derived = derived or item.ref.casefold().startswith(("checkpoint:", "profile_checkpoint:"))
            if derived and item.source_class is not RefClass.DERIVED_CHECKPOINT:
                fail(Issue.CHECKPOINT_AS_EVIDENCE)
            job = item.source_class is RefClass.JOB_HARD_FACT
            if item.owner_id != (request.job_id if job else request.candidate_id):
                fail(Issue.INVALID_SCOPE)
            if item.source_class in {RefClass.CANDIDATE_EVIDENCE, RefClass.CAREER_MEMORY_SOURCE}:
                if item.source_type not in self._candidate_types:
                    fail(Issue.WRONG_SOURCE_CLASS)
                if item.usable_evidence and item.source_type not in {"professional_experience", "career_update"}:
                    fail(Issue.WRONG_SOURCE_CLASS)
            if job and (request.hard_facts is None or item.ref not in request.hard_facts.fact_refs):
                fail(Issue.UNKNOWN_REF)

    def require(self, refs, allowed, *, evidence=False):
        for ref in refs:
            item = self.entries.get(ref)
            if item is None:
                fail(Issue.UNKNOWN_REF)
            if item.source_class is RefClass.DERIVED_CHECKPOINT:
                fail(Issue.CHECKPOINT_AS_EVIDENCE)
            if item.source_class not in allowed or (evidence and not item.usable_evidence):
                fail(Issue.WRONG_SOURCE_CLASS)

    def evidence(self, refs):
        self.require(refs, {RefClass.CANDIDATE_EVIDENCE, RefClass.CAREER_MEMORY_SOURCE}, evidence=True)

    def confirms(self, target):
        return any(
            target in item.confirmed_absence_for
            and item.source_class in {RefClass.CANDIDATE_EVIDENCE, RefClass.CAREER_MEMORY_SOURCE}
            for item in self.entries.values()
        )


def validate_inputs(request, registry):
    if request.schema_version != "structured-interpretation-input-v1":
        fail(Issue.INVALID_SCHEMA)
    if request.operation is Operation.BUILD_CANDIDATE_PROFILE and (
        not request.candidate_id.strip() or not request.memory_signature.strip()
        or request.memory_projection is None
    ):
        fail(Issue.INVALID_SCHEMA)
    if request.operation in {Operation.ANALYZE_HIRING_CASE, Operation.INTERPRET_OPPORTUNITY_VALUE} and (
        request.candidate_profile is None or request.job_profile is None
    ):
        fail(Issue.INVALID_SCHEMA)
    if request.candidate_profile:
        profile = request.candidate_profile
        if profile.candidate_id != request.candidate_id:
            fail(Issue.INVALID_SCOPE)
        unique([item.capability_id for item in profile.capabilities])
        registry.evidence(profile.source_refs)
        for capability in profile.capabilities:
            registry.evidence(capability.evidence_refs)
    if request.hard_facts and request.hard_facts.job_id != request.job_id:
        fail(Issue.INVALID_SCOPE)
    if request.job_profile:
        profile = request.job_profile
        if profile.job_id != request.job_id:
            fail(Issue.INVALID_SCOPE)
        if not request.hard_facts or request.hard_facts.job_signature != profile.job_signature:
            fail(Issue.STALE_INPUT)
        validate_job(JobProfileDraft(profile.needs), request, registry)


def validate_candidate(draft, request, registry, issues):
    unique([item.capability_id for item in draft.capabilities])
    for capability in draft.capabilities:
        registry.evidence(capability.evidence_refs)
    gaps = tuple(gap for gap in draft.confirmed_gaps if registry.confirms(gap))
    unconfirmed = set(draft.confirmed_gaps) - set(gaps)
    if unconfirmed:
        issues.append(Issue.UNCONFIRMED_GAP)
    # Derived checkpoint prose never populates source refs or confirmation state.
    return replace(draft, confirmed_gaps=gaps,
                   evidence_gaps=tuple(sorted(set(draft.evidence_gaps) | unconfirmed)))


def validate_job(draft, request, registry):
    if request.hard_facts is None:
        fail(Issue.INVALID_SCHEMA)
    unique([item.need_id for item in draft.needs])
    facts = {item.fact_id: item for item in request.hard_facts.facts}
    for need in draft.needs:
        registry.require(need.hard_fact_refs, {RefClass.JOB_HARD_FACT})
        registry.require(need.temporal_requirement_refs, {RefClass.JOB_HARD_FACT})
        try:
            validate_temporal_requirement(need, request.hard_facts)
        except ValueError as error:
            fail(Issue(str(error)))
        registry.require(need.evidence_requirement_refs, {RefClass.JOB_HARD_FACT})
        try:
            validate_evidence_requirement(need, request.hard_facts)
        except ValueError:
            fail(Issue.UNSUPPORTED_DIRECT_EVIDENCE_REQUIREMENT)
        if need.hard_blocker and (
            need.authority is not Authority.EXPLICIT
            or not any(facts[ref].hard_blocker for ref in need.hard_fact_refs)
        ):
            fail(Issue.UNSUPPORTED_BLOCKER)
    return draft


def validate_links(payload, request, registry, issues):
    if not request.candidate_profile or not request.job_profile:
        fail(Issue.INVALID_SCHEMA)
    needs = {item.need_id: item for item in request.job_profile.needs}
    if not set(request.source_repair_need_ids) <= set(needs):
        fail(Issue.UNKNOWN_NEED)
    caps = {item.capability_id: item for item in request.candidate_profile.capabilities}
    unique([item.need_id for item in payload.links])
    if set(needs) != {item.need_id for item in payload.links}:
        fail(Issue.UNKNOWN_NEED)
    output = []
    for link in payload.links:
        registry.evidence(link.evidence_refs)
        cap = caps.get(link.candidate_capability_id)
        if link.candidate_capability_id is not None and cap is None:
            fail(Issue.UNKNOWN_CAPABILITY)
        if link.evidence_refs and (cap is None or not set(link.evidence_refs) <= set(cap.evidence_refs)):
            fail(Issue.UNKNOWN_REF)
        state = link.assessment
        if needs[link.need_id].authority is Authority.UNKNOWN:
            issues.append(Issue.UNKNOWN_NEED)
            state = Evidence.EVIDENCE_MISSING
        if state in {Evidence.PROVEN, Evidence.TRANSFERABLE}:
            if not link.evidence_refs or cap is None:
                issues.append(Issue.MISSING_EVIDENCE)
                state = Evidence.EVIDENCE_MISSING
            elif cap.transferable and state is Evidence.PROVEN:
                issues.append(Issue.TRANSFERABLE_PROMOTION)
                state = Evidence.TRANSFERABLE
        if state is Evidence.GAP and not (
            registry.confirms(link.need_id) or registry.confirms(needs[link.need_id].label)
        ):
            issues.append(Issue.UNCONFIRMED_GAP)
            state = Evidence.EVIDENCE_MISSING
        source_repair = state is Evidence.EVIDENCE_MISSING and link.need_id in request.source_repair_need_ids
        reason = {Evidence.PROVEN: LinkReason.DIRECT_SUPPORT, Evidence.TRANSFERABLE: LinkReason.ADJACENT_SUPPORT,
                  Evidence.EVIDENCE_MISSING: LinkReason.NEEDS_EXAMPLE, Evidence.GAP: LinkReason.CONFIRMED_ABSENCE}[state]
        if source_repair:
            reason = LinkReason.SOURCE_REFERENCE_UNAVAILABLE
        refs = link.evidence_refs if state in {Evidence.PROVEN, Evidence.TRANSFERABLE} else ()
        metadata = tuple(TemporalEvidenceMetadata(ref, registry.entries[ref].temporal_need_id,
                         registry.entries[ref].temporal_version, registry.entries[ref].performed_on) for ref in refs)
        try:
            temporal = resolve_temporal_applicability(needs[link.need_id], request.hard_facts, refs, metadata)
        except ValueError as error:
            fail(Issue(str(error)))
        output.append(replace(
            link, assessment=state, needs_evidence=state is Evidence.EVIDENCE_MISSING and not source_repair,
            needs_source_repair=source_repair,
            evidence_question_hint="" if source_repair else link.evidence_question_hint,
            evidence_refs=link.evidence_refs if state in {Evidence.PROVEN, Evidence.TRANSFERABLE} else (),
            confidence=LinkConfidence.LOW if temporal is TemporalApplicability.UNKNOWN else (
                link.confidence if state in {Evidence.PROVEN, Evidence.TRANSFERABLE} else LinkConfidence.UNKNOWN),
            reason_code=reason,
            temporal_applicability=temporal,
            uncertainty="Current applicability is unknown." if temporal is TemporalApplicability.UNKNOWN else link.uncertainty,
        ))
    return SemanticLinks(tuple(output))


def validate_opportunity(payload, request, registry, issues):
    unique([item.kind.value for item in payload.signals])
    unique([item.kind.value for item in request.opportunity_facts])
    facts = {item.kind: item for item in request.opportunity_facts}
    signals = {item.kind: item for item in payload.signals}
    output = []
    for kind in Kind:
        fact = facts.get(kind)
        signal = signals.get(kind)
        if signal:
            registry.require(signal.supporting_refs, {RefClass.JOB_HARD_FACT, RefClass.CAREER_MEMORY_SOURCE, RefClass.CANDIDATE_EVIDENCE})
            if not set(signal.supporting_refs) <= set(fact.supporting_refs if fact else ()):
                fail(Issue.UNSUPPORTED_OPPORTUNITY)
        if fact and fact.conflicting_preference_refs:
            refs = fact.conflicting_preference_refs
            if (len(set(refs)) < 2 or not set(refs) <= set(fact.supporting_refs)
                    or not fact.facts):
                fail(Issue.INVALID_SCHEMA)
            registry.require(refs, {RefClass.CAREER_MEMORY_SOURCE})
            registry.require(fact.supporting_refs, {RefClass.CAREER_MEMORY_SOURCE, RefClass.CANDIDATE_EVIDENCE, RefClass.JOB_HARD_FACT})
            if any(registry.entries[ref].source_type != "candidate_preference" for ref in refs):
                fail(Issue.WRONG_SOURCE_CLASS)
            issues.append(Issue.CONFLICTING_PREFERENCES)
            output.append(InterpretedOpportunitySignal(
                kind, fact.state, SignalState.UNKNOWN, Authority.UNKNOWN, fact.supporting_refs,
                signal.importance if signal else RequirementImportance.IMPORTANT,
                "Current equally authoritative preferences conflict; user clarification is required.",
            ))
            continue
        if not fact or fact.state is FactState.UNKNOWN:
            if signal and (signal.state is not SignalState.UNKNOWN or signal.factual_state is not FactState.UNKNOWN):
                issues.append(Issue.UNKNOWN_OPPORTUNITY_FACT)
            output.append(InterpretedOpportunitySignal(
                kind, FactState.UNKNOWN, SignalState.UNKNOWN, Authority.UNKNOWN, (),
                signal.importance if signal else RequirementImportance.IMPORTANT,
                "Required source facts are unavailable.",
            ))
            continue
        registry.require(fact.supporting_refs, {RefClass.JOB_HARD_FACT, RefClass.CAREER_MEMORY_SOURCE, RefClass.CANDIDATE_EVIDENCE})
        if not fact.supporting_refs or not fact.facts:
            fail(Issue.UNSUPPORTED_OPPORTUNITY)
        if signal is None:
            fail(Issue.INVALID_SCHEMA)
        if signal.factual_state is not FactState.KNOWN:
            fail(Issue.INVALID_SCHEMA)
        if signal.state is not SignalState.UNKNOWN and (
            not signal.supporting_refs or signal.authority is Authority.UNKNOWN
            or set(signal.supporting_refs) != set(fact.supporting_refs)
        ):
            fail(Issue.UNSUPPORTED_OPPORTUNITY)
        output.append(signal)
    return OpportunityInterpretation(tuple(output))


def validate_output(request, raw):
    registry = SourceRefRegistry(request)
    validate_inputs(request, registry)
    schemas = {
        Operation.BUILD_CANDIDATE_PROFILE: CandidateProfileDraft,
        Operation.BUILD_JOB_PROFILE: JobProfileDraft,
        Operation.ANALYZE_HIRING_CASE: SemanticLinks,
        Operation.INTERPRET_OPPORTUNITY_VALUE: OpportunityInterpretation,
    }
    # Report attempted authority elevation specifically, before model construction.
    if request.operation is Operation.BUILD_JOB_PROFILE and isinstance(raw, dict):
        for need in raw.get("needs", ()) if isinstance(raw.get("needs", ()), (tuple, list)) else ():
            if isinstance(need, dict) and need.get("hard_blocker") is True and need.get("authority") != "explicit":
                fail(Issue.UNSUPPORTED_BLOCKER)
    payload = decode_structure(raw, schemas[request.operation])
    issues = []
    if request.operation is Operation.BUILD_CANDIDATE_PROFILE:
        payload = validate_candidate(payload, request, registry, issues)
    elif request.operation is Operation.BUILD_JOB_PROFILE:
        payload = validate_job(payload, request, registry)
    elif request.operation is Operation.ANALYZE_HIRING_CASE:
        payload = validate_links(payload, request, registry, issues)
    else:
        payload = validate_opportunity(payload, request, registry, issues)
    return payload, tuple(sorted(set(issues), key=lambda issue: issue.value))
