from dataclasses import dataclass, fields
from pathlib import Path
import subprocess
import sys
from typing import get_args, get_origin

import pytest

from models.interpretation_boundary import (
    InterpretationRequest, InterpretationResponse, StructuredInterpreter,
)


@dataclass(frozen=True)
class TextInput:
    text: str


@dataclass(frozen=True)
class WordCount:
    count: int


@dataclass(frozen=True)
class Echo:
    text: str


class CountOperation:
    def interpret(self, request: InterpretationRequest[TextInput]) -> InterpretationResponse[WordCount]:
        if request.operation != "test.word-count.v1" or not request.input_payload.text.strip():
            raise ValueError("Invalid count operation input")
        return InterpretationResponse(request.operation, request.input_signature,
                                      WordCount(len(request.input_payload.text.split())))


class EchoOperation:
    def interpret(self, request: InterpretationRequest[TextInput]) -> InterpretationResponse[Echo]:
        if request.operation != "test.echo.v1":
            raise ValueError("Invalid echo operation input")
        return InterpretationResponse(request.operation, request.input_signature, Echo(request.input_payload.text))


def test_independent_operations_share_one_protocol_without_a_result_union():
    counter: StructuredInterpreter[InterpretationRequest[TextInput], InterpretationResponse[WordCount]] = CountOperation()
    echo: StructuredInterpreter[InterpretationRequest[TextInput], InterpretationResponse[Echo]] = EchoOperation()
    request = InterpretationRequest("test.word-count.v1", "input-1", TextInput("Two words"))
    result = counter.interpret(request)
    assert result == InterpretationResponse(request.operation, request.input_signature, WordCount(2))
    second = echo.interpret(InterpretationRequest("test.echo.v1", "input-2", request.input_payload))
    assert second.output_payload == Echo("Two words")
    assert second.input_signature == "input-2"
    assert {f.name for f in fields(request)} == {"operation", "input_signature", "input_payload"}
    assert {f.name for f in fields(result)} == {"operation", "input_signature", "output_payload"}


def test_operation_validation_is_not_in_the_generic_envelope():
    request = InterpretationRequest("test.word-count.v1", "empty-input", TextInput(""))
    with pytest.raises(ValueError, match="Invalid count"):
        CountOperation().interpret(request)
    # Another schema may legitimately allow an empty input.
    assert EchoOperation().interpret(InterpretationRequest("test.echo.v1", "empty-input", TextInput(""))).output_payload == Echo("")


def test_legacy_import_specializes_the_same_verb_and_preserves_fixture_behavior():
    from models.structured_interpretation import (
        StructuredInterpreter as LegacyInterpreter, StructuredInterpretationInput,
        InterpretationResult, ValidationStatus,
    )
    from services.fixture_structured_interpreter import FixtureStructuredInterpreter, fixture_key
    from tests.test_offline_structured_interpreter import request, link

    assert get_origin(LegacyInterpreter) is StructuredInterpreter
    assert get_args(LegacyInterpreter) == (StructuredInterpretationInput, InterpretationResult)
    req = request()
    interpreter: LegacyInterpreter = FixtureStructuredInterpreter({fixture_key(req): link()})
    result = interpreter.interpret(req)
    assert isinstance(result, InterpretationResult)
    assert result.validation_status is ValidationStatus.ACCEPTED
    assert result.operation is req.operation
    assert FixtureStructuredInterpreter({}).interpret(req).validation_status is ValidationStatus.UNAVAILABLE


def test_generic_boundary_imports_only_standard_library():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
class ForbidDependencies:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith('models.') and fullname != 'models.interpretation_boundary') or fullname.split('.')[0] in {
            'services', 'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx', 'components', 'pages',
        }:
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, ForbidDependencies())
from models.interpretation_boundary import InterpretationRequest, InterpretationResponse, StructuredInterpreter
request = InterpretationRequest('test.v1', 'input-id', ('raw text',))
assert InterpretationResponse(request.operation, request.input_signature, 1).output_payload == 1
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
