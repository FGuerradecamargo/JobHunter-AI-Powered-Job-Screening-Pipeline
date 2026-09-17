"""Validate provenance and normalize declared support; never infer meaning from text."""
from dataclasses import asdict, replace
import hashlib
import json
import logging

from models.hiring_case import RequirementEvidenceState as State, TemporalApplicability as Temporal
from models.profile_interpretation import InterpretationAuthority, RequirementLink, TemporalEvidenceMetadata
from models.semantic_evidence import (
    SemanticCoverage as Coverage, SemanticSupportRelation as Relation, SemanticReason as Reason,
    SemanticSupportResponse, SemanticSupportResult, ResolvedSemanticSupport,
)
from models.structured_interpretation import InterpretationOperation, LinkConfidence, ValidationStatus as Status
from services.structured_interpretation_validation import (
    SourceRefRegistry, validate_inputs, decode_structure, InterpretationValidationError,
)
from services.temporal_applicability import resolve_temporal_applicability


class SemanticSupportError(ValueError):
    pass


def signature(request):
    return hashlib.sha256(json.dumps(asdict(request), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require(condition, code):
    if not condition:
        raise SemanticSupportError(code)


def _validate_request(request):
    context = request.context
    require(request.schema_version == "semantic-support-request-v1", "invalid_schema")
    require(context.operation is InterpretationOperation.ANALYZE_HIRING_CASE, "invalid_scope")
    registry = SourceRefRegistry(context)
    validate_inputs(context, registry)
    profile = context.candidate_profile
    require(not context.memory_signature or context.memory_signature == profile.memory_signature, "stale_input")
    refs = [item.ref for item in request.evidence]
    require(len(refs) == len(set(refs)), "invalid_schema")
    registry.evidence(refs)
    require(set(refs) <= set(profile.source_refs), "invalid_scope")
    for source in request.evidence:
        require(source.authority == "source_fact", "invalid_authority")
        require(source.source_type == registry.entries[source.ref].source_type, "invalid_authority")
    return registry


def _shape(relation, coverage, confidence, reason):
    if relation is Relation.NONE:
        require(coverage is Coverage.NONE and reason is Reason.NO_SUPPORT, "inconsistent_support")
    elif relation is Relation.UNCERTAIN:
        require(coverage is Coverage.UNKNOWN and reason in {Reason.INSUFFICIENT_INFORMATION, Reason.CONFLICTING_SOURCES}, "inconsistent_support")
    else:
        require(coverage in {Coverage.FULL, Coverage.PARTIAL}, "inconsistent_support")
        require(reason in {Reason.DIRECT_SUPPORT, Reason.ADJACENT_SUPPORT, Reason.PARTIAL_SUPPORT, Reason.JOINT_SUPPORT}, "inconsistent_support")
    require(isinstance(confidence, LinkConfidence), "invalid_schema")


def _resolve(request, response, registry):
    context = request.context
    needs = {n.need_id: n for n in context.job_profile.needs}
    require(len(response.needs) == len(needs) and {n.need_id for n in response.needs} == set(needs), "unknown_need")
    caps = {c.capability_id: c for c in context.candidate_profile.capabilities}
    available = {e.ref for e in request.evidence}
    output, codes = [], []
    for support in response.needs:
        need = needs[support.need_id]
        _shape(support.support_relation, support.coverage, support.confidence, support.reason_code)
        refs = [link.evidence_ref for link in support.links]
        require(len(refs) == len(set(refs)), "duplicate_relationship")
        registry.evidence(refs)
        require(set(refs) <= available, "unknown_ref")
        for link in support.links:
            require(link.need_id == need.need_id, "unknown_need")
            require(link.interpreter_version == response.interpreter_version, "invalid_version")
            cap = caps.get(link.candidate_capability_id)
            require(link.candidate_capability_id is None or cap is not None, "unknown_capability")
            require(cap is None or link.evidence_ref in cap.evidence_refs, "invalid_scope")
            _shape(link.support_relation, link.coverage, link.confidence, link.reason_code)
        relation, coverage = support.support_relation, support.coverage
        # No selection of the favorable source when the provider reports an unresolved conflict.
        if support.confidence is LinkConfidence.UNKNOWN or support.reason_code is Reason.CONFLICTING_SOURCES or any(
            link.support_relation is Relation.UNCERTAIN or link.confidence is LinkConfidence.UNKNOWN or link.reason_code is Reason.CONFLICTING_SOURCES
            for link in support.links
        ):
            relation, coverage = Relation.UNCERTAIN, Coverage.UNKNOWN
            codes.append("uncertain_support")
        elif relation in {Relation.DIRECT, Relation.ADJACENT}:
            eligible = [link for link in support.links if link.support_relation in {Relation.DIRECT, Relation.ADJACENT}]
            full = [link for link in eligible if link.coverage is Coverage.FULL]
            joint = (support.joint_support and support.reason_code is Reason.JOINT_SUPPORT
                     and len(eligible) >= 2 and len(eligible) == len(support.links))
            if not eligible:
                relation, coverage = Relation.UNCERTAIN, Coverage.UNKNOWN
                codes.append("unsupported_promotion")
            elif coverage is Coverage.FULL and not full and not joint:
                coverage = Coverage.PARTIAL
                codes.append("partial_to_full_overclaim")
            if relation is Relation.DIRECT and not any(l.support_relation is Relation.DIRECT and l.coverage is Coverage.FULL for l in full):
                if any(l.support_relation is Relation.ADJACENT for l in eligible):
                    relation = Relation.ADJACENT
                    codes.append("ownership_promotion")
        if not support.links:
            relation, coverage = Relation.UNCERTAIN, Coverage.UNKNOWN
            if support.support_relation is not Relation.UNCERTAIN:
                codes.append("missing_semantic_evidence")
        state = State.EVIDENCE_MISSING
        supporting = tuple(l.evidence_ref for l in support.links if l.support_relation in {Relation.DIRECT, Relation.ADJACENT})
        if coverage is Coverage.FULL:
            if relation is Relation.DIRECT:
                state = State.PROVEN
            elif relation is Relation.ADJACENT:
                state = State.TRANSFERABLE
        if state is State.PROVEN and any(cap.transferable for cap in caps.values()
                                        if set(cap.evidence_refs) & set(supporting)):
            state = State.TRANSFERABLE
            codes.append("ownership_promotion")
        confirmed = registry.confirms(need.need_id) or registry.confirms(need.label)
        if confirmed:
            if relation is Relation.NONE:
                state = State.GAP
            elif relation in {Relation.DIRECT, Relation.ADJACENT}:
                state, relation, coverage = State.EVIDENCE_MISSING, Relation.UNCERTAIN, Coverage.UNKNOWN
                codes.append("conflicting_evidence")
        if need.authority is InterpretationAuthority.UNKNOWN:
            state = State.EVIDENCE_MISSING
        metadata = tuple(TemporalEvidenceMetadata(ref, registry.entries[ref].temporal_need_id,
                         registry.entries[ref].temporal_version, registry.entries[ref].performed_on) for ref in supporting)
        temporal = resolve_temporal_applicability(need, context.hard_facts, supporting, metadata)
        # Preserve historical support but do not certify current proficiency as PROVEN.
        if state is State.PROVEN and temporal in {Temporal.NOT_SATISFIED, Temporal.UNKNOWN}:
            state = State.TRANSFERABLE
            codes.append("current_support_unestablished")
        reason = support.reason_code
        if relation is Relation.UNCERTAIN:
            reason = Reason.CONFLICTING_SOURCES if confirmed or reason is Reason.CONFLICTING_SOURCES else Reason.INSUFFICIENT_INFORMATION
        elif coverage is Coverage.PARTIAL:
            reason = Reason.PARTIAL_SUPPORT
        elif relation is Relation.ADJACENT and reason is Reason.DIRECT_SUPPORT:
            reason = Reason.ADJACENT_SUPPORT
        normalized = replace(support, support_relation=relation, coverage=coverage, reason_code=reason,
                             confidence=LinkConfidence.UNKNOWN if relation is Relation.UNCERTAIN else support.confidence)
        output.append(ResolvedSemanticSupport(normalized, state, supporting, temporal))
    return tuple(output), tuple(sorted(set(codes)))


def validate_semantic_support(request, raw):
    """Accept strict structured output, bound to all current source/profile versions."""
    key = signature(request)
    try:
        registry = _validate_request(request)
        response = decode_structure(asdict(raw) if isinstance(raw, SemanticSupportResponse) else raw, SemanticSupportResponse)
        require(response.schema_version == "semantic-support-response-v1", "invalid_schema")
        require(response.input_signature == key, "stale_input")
        require(bool(response.interpreter_version.strip()), "invalid_version")
        needs, codes = _resolve(request, response, registry)
        result = SemanticSupportResult(key, Status.NORMALIZED if codes else Status.ACCEPTED, needs, codes)
    except InterpretationValidationError as error:
        result = SemanticSupportResult(key, Status.REJECTED, issue_codes=(error.code.value,))
    except SemanticSupportError as error:
        result = SemanticSupportResult(key, Status.REJECTED, issue_codes=(str(error),))
    except (ValueError, TypeError, AttributeError):
        result = SemanticSupportResult(key, Status.REJECTED, issue_codes=("invalid_schema",))
    logging.getLogger(__name__).info("semantic_support status=%s codes=%s count=%d", result.status.value, result.issue_codes, len(result.needs))
    return result


def semantic_requirement_links(request, raw):
    """Revalidate at the adapter boundary; a forged accepted envelope has no authority."""
    result = validate_semantic_support(request, raw)
    require(result.status in {Status.ACCEPTED, Status.NORMALIZED}, "semantic_support_unavailable")
    return tuple(RequirementLink(item.support.need_id, item.assessment,
                 item.supporting_refs if item.assessment in {State.PROVEN, State.TRANSFERABLE} else (),
                 "semantic_support_v1", item.assessment in {State.PROVEN, State.TRANSFERABLE}) for item in result.needs)
