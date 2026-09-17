"""Exact request lookup of controlled provider responses. No semantic fallback or IO."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import logging

from models.structured_interpretation import (
    InterpretationResult, SemanticLinks, StructuredInterpretationInput,
    ValidationIssue as Issue, ValidationStatus as Status,
)
from services.structured_interpretation_validation import InterpretationValidationError, validate_output


def input_signature(request: StructuredInterpretationInput) -> str:
    content = json.dumps(asdict(request), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def fixture_key(request):
    return request.operation, input_signature(request)


def validate_response(request, raw, *, produced_at, interpreter_version):
    """The same boundary can validate a future provider adapter's decoded JSON."""
    try:
        payload, issues = validate_output(request, raw)
        status = Status.NORMALIZED if issues else Status.ACCEPTED
    except InterpretationValidationError as error:
        payload, issues, status = None, (error.code,), Status.REJECTED
    return InterpretationResult(
        request.operation, input_signature(request), payload, produced_at,
        status, issues, interpreter_version=interpreter_version,
    )


def diagnostic_event(result):
    event = {
        "event": "structured_interpretation", "operation": result.operation.value,
        "result": result.validation_status.value, "authoritative": False,
        "issue_codes": [issue.value for issue in result.validation_issue_codes],
        "invalid_refs": sum(issue in {Issue.UNKNOWN_REF, Issue.WRONG_SOURCE_CLASS, Issue.CHECKPOINT_AS_EVIDENCE}
                            for issue in result.validation_issue_codes),
    }
    if isinstance(result.output_payload, SemanticLinks):
        event["requirements"] = len(result.output_payload.links)
        for state in ("proven", "transferable", "evidence_missing", "gap"):
            event[state] = sum(link.assessment.value == state for link in result.output_payload.links)
    return event


class FixtureStructuredInterpreter:
    version = "fixture-structured-interpreter-v1"

    def __init__(self, responses, *, clock=None):
        self._responses = deepcopy(dict(responses))
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def interpret(self, request: StructuredInterpretationInput) -> InterpretationResult:
        # Snapshot caller-owned input to bind validation to the exact lookup key.
        request = deepcopy(request)
        key = fixture_key(request)
        if key not in self._responses:
            result = InterpretationResult(
                request.operation, key[1], None, self._clock(), Status.UNAVAILABLE,
                (Issue.FIXTURE_UNAVAILABLE,), interpreter_version=self.version,
            )
        else:
            result = validate_response(request, deepcopy(self._responses[key]),
                                       produced_at=self._clock(), interpreter_version=self.version)
        logging.getLogger(__name__).info("%s", json.dumps(diagnostic_event(result), sort_keys=True))
        return result
