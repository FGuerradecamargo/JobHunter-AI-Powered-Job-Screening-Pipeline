"""Execution specification for ProfessionalFacts; no provider construction or IO."""
from dataclasses import asdict
import json

from pydantic import BaseModel, ConfigDict

from models.candidate_past import ProfessionalFact
from models.interpretation_boundary import InterpretationRequest
from services.interpretation_operation_spec import InterpretationOperationSpec
from services.professional_facts_operation import (
    INSTRUCTIONS, OPERATION, ProfessionalFactsInput, ProfessionalFactsOutput,
    build_request, validate_response, professional_fact_id,
)


class _FactOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    statement: str
    candidate_input_id: str


class ProfessionalFactsStructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    facts: list[_FactOutput]


def _validate_request(request: InterpretationRequest[ProfessionalFactsInput]) -> None:
    if request != build_request(request.input_payload):
        raise ValueError("Invalid ProfessionalFacts request identity.")


def _serialize_input(payload: ProfessionalFactsInput) -> str:
    return json.dumps(asdict(payload), ensure_ascii=True, sort_keys=True)


def _parse_output(raw: dict) -> ProfessionalFactsOutput:
    structured = ProfessionalFactsStructuredOutput.model_validate(raw)
    return ProfessionalFactsOutput(tuple(
        ProfessionalFact(professional_fact_id(item.candidate_input_id, item.statement),
                         item.statement, item.candidate_input_id)
        for item in structured.facts
    ))


PROFESSIONAL_FACTS_SPEC = InterpretationOperationSpec[ProfessionalFactsInput, ProfessionalFactsOutput](
    operation=OPERATION,
    instructions=INSTRUCTIONS,
    response_model=ProfessionalFactsStructuredOutput,
    validate_request=_validate_request,
    serialize_input=_serialize_input,
    parse_output=_parse_output,
    validate_response=validate_response,
)
