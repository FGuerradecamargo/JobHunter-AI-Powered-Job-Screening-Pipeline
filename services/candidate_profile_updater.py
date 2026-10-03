"""Snapshot-first update tool; callers supply confirmed, typed source events."""
from dataclasses import asdict, fields
from datetime import datetime, timezone
import hashlib
import json
import sqlite3

import psycopg

from models.candidate_profile_update import CandidateProfileSourceSync, CandidateProfileUpdateInput
from models.profile_interpretation import CandidateProfileDraft, CandidateProfileSnapshot
from models.structured_interpretation import (
    InterpretationOperation, StructuredInterpretationInput, StructuredInterpreter,
    ValidationIssue, ValidationStatus,
)
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.structured_interpretation_validation import (
    InterpretationValidationError, SourceRefRegistry, validate_inputs, validate_output,
)


def _signature(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class CandidateProfileUpdater:
    def __init__(self, repository: ProfileSnapshotRepository, interpreter: StructuredInterpreter, *, clock=None):
        self._repository = repository
        self._interpreter = interpreter
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def update(self, current_snapshot: CandidateProfileSnapshot,
               update_input: CandidateProfileUpdateInput, *,
               source_sync: CandidateProfileSourceSync | None = None) -> CandidateProfileSnapshot:
        if current_snapshot.candidate_id != update_input.candidate_id:
            raise InterpretationValidationError(ValidationIssue.INVALID_SCOPE)
        if source_sync is not None and (
            source_sync.candidate_id != current_snapshot.candidate_id
            or source_sync.update_id != update_input.update_id
        ):
            raise InterpretationValidationError(ValidationIssue.INVALID_SCOPE)
        identity = {"snapshot": asdict(current_snapshot), "update": asdict(update_input)}
        if source_sync is not None:
            identity["source_sync"] = asdict(source_sync)
        signature = _signature(identity)
        request = StructuredInterpretationInput(
            operation=InterpretationOperation.UPDATE_CANDIDATE_PROFILE,
            candidate_id=current_snapshot.candidate_id,
            memory_signature=signature,
            candidate_profile=current_snapshot,
            candidate_update=update_input,
            source_registry=(*current_snapshot.source_registry, update_input.source),
        )
        validate_inputs(request, SourceRefRegistry(request))
        existing = self._repository.candidate_for_signature(
            current_snapshot.candidate_id, signature, current_snapshot.schema_version)
        if existing is not None:
            return existing
        if self._repository.current_candidate(current_snapshot.candidate_id) != current_snapshot:
            raise InterpretationValidationError(ValidationIssue.STALE_INPUT)

        result = self._interpreter.interpret(request)
        if (result.operation is not request.operation
                or result.input_signature != _signature(asdict(request))
                or result.validation_status not in {ValidationStatus.ACCEPTED, ValidationStatus.NORMALIZED}
                or not isinstance(result.output_payload, CandidateProfileDraft)):
            raise InterpretationValidationError(ValidationIssue.INVALID_SCHEMA)
        # Never trust an adapter's claim that its response was already validated.
        draft, _ = validate_output(request, asdict(result.output_payload))
        profile = CandidateProfileSnapshot(
            candidate_id=current_snapshot.candidate_id,
            profile_version=current_snapshot.profile_version + 1,
            supersedes_version=current_snapshot.profile_version,
            memory_signature=signature,
            raw_source_signature=source_sync.raw_source_signature if source_sync is not None else "",
            created_at=self._clock(),
            schema_version=current_snapshot.schema_version,
            source_refs=(*current_snapshot.source_refs, update_input.source.ref),
            source_registry=request.source_registry,
            **{field.name: getattr(draft, field.name) for field in fields(CandidateProfileDraft)},
        )
        try:
            self._repository.save_candidate(profile)
        except (sqlite3.IntegrityError, psycopg.IntegrityError):
            # Same update wins reuse; a different writer's version is never overwritten.
            existing = self._repository.candidate_for_signature(
                profile.candidate_id, signature, profile.schema_version)
            if existing is None:
                raise InterpretationValidationError(ValidationIssue.STALE_INPUT) from None
            return existing
        return profile
