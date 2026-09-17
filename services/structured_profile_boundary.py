"""Convert validated, request-bound interpretations into existing domain contracts."""
from dataclasses import asdict

from models.hiring_case import OpportunitySignal, RequirementEvidenceState
from models.profile_interpretation import CandidateProfileSnapshot, AIJobProfileSnapshot, HiringCaseInterpretation, RequirementLink
from models.structured_interpretation import InterpretationOperation as Operation, ValidationIssue as Issue, ValidationStatus as Status
from services.fixture_structured_interpreter import input_signature, validate_response
from services.structured_interpretation_validation import InterpretationValidationError
from models.profile_interpretation import TemporalEvidenceMetadata
from models.structured_interpretation import SourceRefClass


def accepted_payload(request, result, operation):
    if (request.operation is not operation or result.operation is not operation
            or result.input_signature != input_signature(request)
            or result.schema_version != "structured-interpretation-result-v1" or result.authoritative):
        raise InterpretationValidationError(Issue.STALE_INPUT)
    if result.validation_status not in {Status.ACCEPTED, Status.NORMALIZED} or result.output_payload is None:
        raise InterpretationValidationError(Issue.FIXTURE_UNAVAILABLE)
    # An envelope is not a source of authority: revalidate even a forged accepted result.
    checked = validate_response(request, asdict(result.output_payload), produced_at=result.produced_at,
                                interpreter_version=result.interpreter_version)
    if checked.validation_status is Status.REJECTED:
        raise InterpretationValidationError(checked.validation_issue_codes[0])
    return checked.output_payload


def candidate_snapshot(request, result, *, version=1, supersedes_version=None):
    draft = accepted_payload(request, result, Operation.BUILD_CANDIDATE_PROFILE)
    return CandidateProfileSnapshot(
        candidate_id=request.candidate_id, profile_version=version,
        memory_signature=request.memory_signature, created_at=result.produced_at,
        source_refs=tuple(sorted({ref for cap in draft.capabilities for ref in cap.evidence_refs})),
        supersedes_version=supersedes_version, **as_domain_fields(draft),
    )


def as_domain_fields(draft):
    # Keep nested immutable domain objects; asdict would turn them into loose maps.
    return {name: getattr(draft, name) for name in draft.__dataclass_fields__}


def job_snapshot(request, result, *, version=1, supersedes_version=None):
    draft = accepted_payload(request, result, Operation.BUILD_JOB_PROFILE)
    return AIJobProfileSnapshot(
        job_id=request.job_id, profile_version=version, job_signature=request.hard_facts.job_signature,
        created_at=result.produced_at, supersedes_version=supersedes_version, **as_domain_fields(draft),
    )


def hiring_interpretation(pair_request, pair_result, value_request, value_result):
    links = accepted_payload(pair_request, pair_result, Operation.ANALYZE_HIRING_CASE)
    value = accepted_payload(value_request, value_result, Operation.INTERPRET_OPPORTUNITY_VALUE)
    if (pair_request.candidate_profile != value_request.candidate_profile
            or pair_request.job_profile != value_request.job_profile
            or pair_request.source_registry != value_request.source_registry
            or pair_request.hard_facts != value_request.hard_facts):
        raise InterpretationValidationError(Issue.INVALID_SCOPE)
    return HiringCaseInterpretation(
        tuple(RequirementLink(
            link.need_id, link.assessment, link.evidence_refs, link.reason_code.value,
            link.assessment in {RequirementEvidenceState.PROVEN, RequirementEvidenceState.TRANSFERABLE},
        ) for link in links.links),
        tuple(OpportunitySignal(item.kind, item.state, item.importance) for item in value.signals),
        seniority_context_mismatch=pair_request.seniority_context_mismatch,
        temporal_evidence=tuple(TemporalEvidenceMetadata(item.ref, item.temporal_need_id,
                                item.temporal_version, item.performed_on)
            for item in pair_request.source_registry
            if item.usable_evidence and item.source_class in {SourceRefClass.CANDIDATE_EVIDENCE, SourceRefClass.CAREER_MEMORY_SOURCE}),
    )
