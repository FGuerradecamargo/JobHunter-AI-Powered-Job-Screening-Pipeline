from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict
import pytest

from models.candidate_past import CandidateInput, ProfessionalFact
from models.interpretation_boundary import InterpretationRequest, InterpretationResponse, StructuredInterpreter
from services.ai_structured_interpreter import AIStructuredInterpreter, InterpretationExecutionError
from services.interpretation_operation_spec import InterpretationOperationSpec
from services.professional_facts_operation import (
    INSTRUCTIONS, ProfessionalFactsInput, ProfessionalFactsOutput, build_request, validate_response, professional_fact_id,
)
from services.professional_facts_spec import PROFESSIONAL_FACTS_SPEC, ProfessionalFactsStructuredOutput


class FakeProvider:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def generate_structured(self, prompt, response_model):
        self.calls.append((prompt, response_model))
        if self.error is not None:
            raise self.error
        return self.result


def _request():
    return build_request(ProfessionalFactsInput((CandidateInput("input-1", "I used SQL."),)))


def _raw():
    return {"facts": [{"statement": "Used SQL.", "candidate_input_id": "input-1"}]}


def test_professional_facts_through_generic_verb():
    request = _request()
    provider = FakeProvider(_raw())
    interpreter: StructuredInterpreter[
        InterpretationRequest[ProfessionalFactsInput], InterpretationResponse[ProfessionalFactsOutput]
    ] = AIStructuredInterpreter(provider, PROFESSIONAL_FACTS_SPEC)
    response = interpreter.interpret(request)
    assert response.operation == request.operation
    assert response.input_signature == request.input_signature
    assert response.output_payload == ProfessionalFactsOutput((ProfessionalFact(professional_fact_id("input-1", "Used SQL."), "Used SQL.", "input-1"),))
    assert validate_response(request, response) is response
    assert len(provider.calls) == 1
    prompt, schema = provider.calls[0]
    assert prompt.startswith(INSTRUCTIONS)
    assert schema is ProfessionalFactsStructuredOutput
    assert json.loads(prompt.split("\n\nINPUT DATA:\n", 1)[1]) == {
        "inputs": [{"id": "input-1", "original_text": "I used SQL."}],
    }


def test_empty_facts_are_valid_not_fabricated():
    result = AIStructuredInterpreter(FakeProvider({"facts": []}), PROFESSIONAL_FACTS_SPEC).interpret(_request())
    assert result.output_payload.facts == ()


@pytest.mark.parametrize("raw", [
    None, '{"facts": []}', [], {}, {"facts": "text"}, {"facts": [], "extra": True},
    {"facts": [{"statement": "x"}]},
    {"facts": [{"id": 1, "statement": "x", "candidate_input_id": "input-1"}]},
    {"facts": [{"statement": " ", "candidate_input_id": "input-1"}]},
    {"facts": [{"statement": "x", "candidate_input_id": "input-1", "extra": True}]},
])
def test_invalid_structured_output_fails_explicitly(raw):
    provider = FakeProvider(raw)
    with pytest.raises(InterpretationExecutionError, match="^invalid_output$"):
        AIStructuredInterpreter(provider, PROFESSIONAL_FACTS_SPEC).interpret(_request())
    assert len(provider.calls) == 1


@pytest.mark.parametrize("source", ["unknown", professional_fact_id("input-1", "Used SQL.")])
def test_operation_rejects_unknown_or_fact_to_fact_provenance(source):
    raw = _raw()
    raw["facts"].append({"statement": "Second fact.", "candidate_input_id": source})
    with pytest.raises(InterpretationExecutionError, match="^invalid_output$"):
        AIStructuredInterpreter(FakeProvider(raw), PROFESSIONAL_FACTS_SPEC).interpret(_request())


def test_duplicate_fact_ids_rejected():
    raw = _raw()
    raw["facts"] *= 2
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        AIStructuredInterpreter(FakeProvider(raw), PROFESSIONAL_FACTS_SPEC).interpret(_request())


@pytest.mark.parametrize("changes", [
    {"operation": "other.v1"}, {"input_signature": "stale"}, {"input_payload": "not typed input"},
])
def test_invalid_requests_never_reach_provider(changes):
    provider = FakeProvider(_raw())
    with pytest.raises(InterpretationExecutionError, match="^invalid_request$"):
        AIStructuredInterpreter(provider, PROFESSIONAL_FACTS_SPEC).interpret(replace(_request(), **changes))
    assert provider.calls == []


def test_provider_failure_is_explicit_without_payload_or_retry(caplog):
    marker = "private-provider-body-secret"
    provider = FakeProvider(error=RuntimeError(marker))
    parser_calls = []
    spec = replace(PROFESSIONAL_FACTS_SPEC, parse_output=lambda raw: parser_calls.append(raw))
    with pytest.raises(InterpretationExecutionError, match="^provider_execution_failed$") as caught:
        AIStructuredInterpreter(provider, spec).interpret(_request())
    assert marker not in str(caught.value)
    assert marker not in caplog.text
    assert caught.value.__suppress_context__
    assert parser_calls == []
    assert len(provider.calls) == 1


def test_unrelated_operation_owns_serialization_schema_conversion_and_validation():
    class CountSchema(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        count: int

    calls = []

    def validate_request(request):
        calls.append("request")
        assert request.input_payload == ("a", "b")

    def serialize(payload):
        calls.append("serialize")
        return "|".join(payload)

    def parse(raw):
        calls.append("parse")
        return CountSchema.model_validate(raw).count

    def validate(request, response):
        calls.append("validate")
        assert response.output_payload == len(request.input_payload)

    spec = InterpretationOperationSpec(
        "count.v1", "Count supplied entries.", CountSchema,
        validate_request, serialize, parse, validate,
    )
    provider = FakeProvider({"count": 2})
    response = AIStructuredInterpreter(provider, spec).interpret(InterpretationRequest("count.v1", "identity", ("a", "b")))
    assert response == InterpretationResponse("count.v1", "identity", 2)
    assert calls == ["request", "serialize", "parse", "validate"]
    assert provider.calls == [("Count supplied entries.\n\nINPUT DATA:\na|b", CountSchema)]


def test_existing_openai_structured_transport_with_fake_sdk():
    from services.ai.openai_client import OpenAIClient

    calls = []

    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_parsed=kwargs["text_format"].model_validate(_raw()))

    # Skip credential loading/client construction; SDK execution is a local double.
    provider = OpenAIClient.__new__(OpenAIClient)
    provider.model = "offline-test"
    provider.client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    response = AIStructuredInterpreter(provider, PROFESSIONAL_FACTS_SPEC).interpret(_request())
    assert response.output_payload.facts[0].id == professional_fact_id("input-1", "Used SQL.")
    assert len(calls) == 1
    assert calls[0]["text_format"] is ProfessionalFactsStructuredOutput


def test_import_and_fake_execution_require_no_runtime_or_domain_construction():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
allowed_services = {
    'services.ai_structured_interpreter', 'services.interpretation_operation_spec',
    'services.professional_facts_spec', 'services.professional_facts_operation',
}
allowed_models = {'models.candidate_past', 'models.interpretation_boundary'}
class ForbidDependencies:
    def find_spec(self, fullname, path=None, target=None):
        if ((fullname.startswith('services.') and fullname not in allowed_services)
            or (fullname.startswith('models.') and fullname not in allowed_models)
            or fullname.split('.')[0] in {'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx'}):
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, ForbidDependencies())
from services.ai_structured_interpreter import AIStructuredInterpreter
from services.professional_facts_spec import PROFESSIONAL_FACTS_SPEC
from services.professional_facts_operation import ProfessionalFactsInput, build_request
import models.candidate_past as past
def forbidden(*args, **kwargs):
    raise AssertionError('Domain aggregate construction forbidden')
past.CandidatePast = past.Experience = past.Education = past.Certification = forbidden
class Provider:
    def generate_structured(self, prompt, response_model):
        return {'facts': []}
request = build_request(ProfessionalFactsInput((past.CandidateInput('i', 'Original'),)))
assert AIStructuredInterpreter(Provider(), PROFESSIONAL_FACTS_SPEC).interpret(request).output_payload.facts == ()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_provider_fact_identity_is_forbidden_even_if_canonical():
    raw = _raw()
    raw["facts"][0]["id"] = professional_fact_id("input-1", "Used SQL.")
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        AIStructuredInterpreter(FakeProvider(raw), PROFESSIONAL_FACTS_SPEC).interpret(_request())
    schema = ProfessionalFactsStructuredOutput.model_json_schema()
    assert set(schema["$defs"]["_FactOutput"]["properties"]) == {"statement", "candidate_input_id"}
