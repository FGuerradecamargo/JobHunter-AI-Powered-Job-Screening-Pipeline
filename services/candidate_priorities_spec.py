"""Structured transport for preference rules; IDs remain locally controlled."""
from dataclasses import asdict
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.candidate_priorities import CandidatePriorities, Priority, PriorityEffect, PriorityValue
from services.candidate_priorities_operation import (
    INSTRUCTIONS, OPERATION, CandidatePrioritiesInput, build_request, priority_id, validate_response,
)
from services.interpretation_operation_spec import InterpretationOperationSpec


class _PriorityOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    subject: str
    operator: str
    value: PriorityValue
    effect: PriorityEffect = Field(strict=False)

    @field_validator("value", mode="before")
    @classmethod
    def exact_scalar(cls, value):
        if type(value) not in (str, int, float, bool):
            raise ValueError("Expected an exact built-in scalar.")
        return value


class CandidatePrioritiesStructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    priorities: list[_PriorityOutput]


def _validate_request(request) -> None:
    if request != build_request(request.input_payload):
        raise ValueError("Invalid CandidatePriorities request identity.")


def _serialize_input(payload: CandidatePrioritiesInput) -> str:
    return json.dumps(asdict(payload), sort_keys=True, ensure_ascii=True)


def _parse_output(raw: dict) -> CandidatePriorities:
    result = CandidatePrioritiesStructuredOutput.model_validate(raw)
    return CandidatePriorities(tuple(
        Priority(priority_id(item.subject, item.operator, item.value, item.effect),
                 item.subject, item.operator, item.value, item.effect)
        for item in result.priorities
    ))


CANDIDATE_PRIORITIES_SPEC = InterpretationOperationSpec[CandidatePrioritiesInput, CandidatePriorities](
    operation=OPERATION, instructions=INSTRUCTIONS, response_model=CandidatePrioritiesStructuredOutput,
    validate_request=_validate_request, serialize_input=_serialize_input,
    parse_output=_parse_output, validate_response=validate_response,
)
