"""Injected operation execution specification; independent of any AI vendor."""
from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar

from pydantic import BaseModel

from models.interpretation_boundary import InterpretationRequest, InterpretationResponse

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class StructuredOutputProvider(Protocol):
    def generate_structured(self, prompt: str, response_model: type[BaseModel]) -> dict: ...


@dataclass(frozen=True)
class InterpretationOperationSpec(Generic[InputT, OutputT]):
    """Operation-owned transport schema and hooks, not a central operation registry.

    Response validation must raise on invalid results; its return is not used.
    Schema validation/conversion belongs to parse_output, not the generic adapter.
    """

    operation: str
    instructions: str
    response_model: type[BaseModel]
    validate_request: Callable[[InterpretationRequest[InputT]], None]
    serialize_input: Callable[[InputT], str]
    parse_output: Callable[[dict], OutputT]
    validate_response: Callable[
        [InterpretationRequest[InputT], InterpretationResponse[OutputT]], object
    ]
