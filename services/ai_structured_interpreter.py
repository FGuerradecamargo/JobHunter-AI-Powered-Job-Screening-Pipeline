"""One interpretation verb, composed with an operation and structured provider."""
from typing import Generic, TypeVar

from models.interpretation_boundary import InterpretationRequest, InterpretationResponse
from services.interpretation_operation_spec import InterpretationOperationSpec, StructuredOutputProvider

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class InterpretationExecutionError(RuntimeError):
    """Safe stage-only failure; never includes input, provider body or credentials."""


class AIStructuredInterpreter(Generic[InputT, OutputT]):
    def __init__(
        self, provider: StructuredOutputProvider,
        specification: InterpretationOperationSpec[InputT, OutputT],
    ) -> None:
        self._provider = provider
        self._spec = specification

    def interpret(self, request: InterpretationRequest[InputT]) -> InterpretationResponse[OutputT]:
        try:
            if type(request) is not InterpretationRequest or request.operation != self._spec.operation:
                raise ValueError("Operation mismatch.")
            self._spec.validate_request(request)
            serialized = self._spec.serialize_input(request.input_payload)
            if not isinstance(serialized, str):
                raise TypeError("Serialized input must be text.")
        except Exception:
            raise InterpretationExecutionError("invalid_request") from None

        prompt = self._spec.instructions + "\n\nINPUT DATA:\n" + serialized
        try:
            raw = self._provider.generate_structured(prompt, self._spec.response_model)
        except Exception:
            raise InterpretationExecutionError("provider_execution_failed") from None

        try:
            if not isinstance(raw, dict):
                raise TypeError("Expected structured provider output.")
            output = self._spec.parse_output(raw)
            response = InterpretationResponse(request.operation, request.input_signature, output)
            self._spec.validate_response(request, response)
        except Exception:
            raise InterpretationExecutionError("invalid_output") from None
        return response
