"""Structured transport for declared direction, without domain orchestration."""
from dataclasses import asdict
import json

from pydantic import BaseModel, ConfigDict

from models.candidate_future import CandidateFuture
from services.candidate_future_operation import (
    INSTRUCTIONS, OPERATION, CandidateFutureInput, build_request, validate_response,
)
from services.interpretation_operation_spec import InterpretationOperationSpec


class CandidateFutureStructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    target_area: str | None
    target_role: str | None


def _validate_request(request) -> None:
    if request != build_request(request.input_payload):
        raise ValueError("Invalid CandidateFuture request identity.")


def _serialize_input(payload: CandidateFutureInput) -> str:
    return json.dumps(asdict(payload), sort_keys=True, ensure_ascii=True)


def _parse_output(raw: dict) -> CandidateFuture:
    result = CandidateFutureStructuredOutput.model_validate(raw)
    return CandidateFuture(result.target_area, result.target_role)


CANDIDATE_FUTURE_SPEC = InterpretationOperationSpec[CandidateFutureInput, CandidateFuture](
    operation=OPERATION, instructions=INSTRUCTIONS, response_model=CandidateFutureStructuredOutput,
    validate_request=_validate_request, serialize_input=_serialize_input,
    parse_output=_parse_output, validate_response=validate_response,
)
