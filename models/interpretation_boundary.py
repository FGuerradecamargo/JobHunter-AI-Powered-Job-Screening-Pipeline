"""One interpretation verb, with operation-owned schemas and validation.

Implementations interpret and validate; callers construct and persist domain state.
Payload types may carry operation-specific context. Envelopes do not validate
domain semantics, choose prompts, dispatch operations, or resolve identities.
"""
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")
RequestT = TypeVar("RequestT", contravariant=True)
ResultT = TypeVar("ResultT", covariant=True)


@dataclass(frozen=True)
class InterpretationRequest(Generic[InputT]):
    """Operation identity (including its schema version), input identity and data."""

    operation: str
    input_signature: str
    input_payload: InputT


@dataclass(frozen=True)
class InterpretationResponse(Generic[OutputT]):
    """Typed result bound to its request; validation belongs to the operation.

    OutputT may represent an operation's validated success or structured failure.
    Constructing this envelope alone is not proof that validation took place.
    """

    operation: str
    input_signature: str
    output_payload: OutputT


class StructuredInterpreter(Protocol[RequestT, ResultT]):
    def interpret(self, request: RequestT) -> ResultT: ...
