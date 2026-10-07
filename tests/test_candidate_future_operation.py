from dataclasses import FrozenInstanceError, fields, replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_future import CandidateFuture
from models.interpretation_boundary import InterpretationResponse
from services.ai_structured_interpreter import AIStructuredInterpreter, InterpretationExecutionError
from services.candidate_future_operation import (
    INSTRUCTIONS, CandidateDeclaration, CandidateFutureInput, build_request, validate_response,
)
from services.candidate_future_spec import CANDIDATE_FUTURE_SPEC, CandidateFutureStructuredOutput


def _request(text="I want to work in Data."):
    return build_request(CandidateFutureInput((CandidateDeclaration("d1", text),)))


class Provider:
    def __init__(self, output=None, error=None):
        self.output, self.error, self.calls = output, error, []

    def generate_structured(self, prompt, schema):
        self.calls.append((prompt, schema))
        if self.error is not None:
            raise self.error
        return self.output


def test_identity_binds_exact_source_id_and_text():
    assert _request() == _request()
    assert _request("different").input_signature != _request().input_signature
    changed = build_request(CandidateFutureInput((CandidateDeclaration("other", "I want to work in Data."),)))
    assert changed.input_signature != _request().input_signature
    declaration = CandidateDeclaration(" d1 ", "  Data\nEngineer  ")
    assert (declaration.id, declaration.text) == (" d1 ", "  Data\nEngineer  ")
    with pytest.raises(FrozenInstanceError):
        declaration.text = "other"


@pytest.mark.parametrize("invalid", [[], ({"desired_next_work": "Data"},), ("Data",)])
def test_input_requires_declarations_not_onboarding_objects(invalid):
    with pytest.raises(TypeError):
        CandidateFutureInput(invalid)


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        CandidateFutureInput((CandidateDeclaration("d", "Data"), CandidateDeclaration("d", "Engineering")))


@pytest.mark.parametrize("identity", ["", "  ", None, 1])
def test_nonblank_identity_required(identity):
    with pytest.raises(ValueError):
        CandidateDeclaration(identity, "")


@pytest.mark.parametrize("text", [None, 1, {}, []])
def test_text_must_be_string(text):
    with pytest.raises(TypeError):
        CandidateDeclaration("d", text)


@pytest.mark.parametrize("text, area, role", [
    ("I would like to work in Data", "Data", None),
    ("I want to become a Data Engineer", "Data", "Data Engineer"),
    ("I eventually want to become a Senior Software Engineer", None, "Senior Software Engineer"),
    ("I want something different but I am not sure what", None, None),
    ("", None, None),
    ("I want remote work", None, None),
    ("I currently work in customer support", None, None),
    ("I want to work in Data, remotely", "Data", None),
])
def test_controlled_outputs_demonstrate_contract_not_live_semantic_accuracy(text, area, role):
    provider = Provider({"target_area": area, "target_role": role})
    request = _request(text)
    response = AIStructuredInterpreter(provider, CANDIDATE_FUTURE_SPEC).interpret(request)
    assert type(response.output_payload) is CandidateFuture
    assert response.output_payload == CandidateFuture(area, role)
    assert validate_response(request, response) is response
    prompt, schema = provider.calls[0]
    assert schema is CandidateFutureStructuredOutput
    assert prompt.startswith(INSTRUCTIONS)
    assert json.loads(prompt.split("\n\nINPUT DATA:\n", 1)[1]) == {
        "declarations": [{"id": "d1", "text": text}],
    }


def test_empty_collection_valid():
    request = build_request(CandidateFutureInput(()))
    result = AIStructuredInterpreter(Provider({"target_area": None, "target_role": None}), CANDIDATE_FUTURE_SPEC).interpret(request)
    assert result.output_payload == CandidateFuture()


@pytest.mark.parametrize("output", [
    None, [], "{}", {}, {"target_area": None},
    {"target_area": "", "target_role": None},
    {"target_area": None, "target_role": "  "},
    {"target_area": 1, "target_role": None},
    {"target_area": None, "target_role": []},
    {"target_area": None, "target_role": None, "skills": []},
])
def test_malformed_output_fails(output):
    with pytest.raises(InterpretationExecutionError, match="^invalid_output$"):
        AIStructuredInterpreter(Provider(output), CANDIDATE_FUTURE_SPEC).interpret(_request())


@pytest.mark.parametrize("extra", ["confidence", "gaps", "next_step", "action_plan", "market_requirements"])
def test_extra_domain_fields_forbidden(extra):
    raw = {"target_area": None, "target_role": None, extra: "invented"}
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        AIStructuredInterpreter(Provider(raw), CANDIDATE_FUTURE_SPEC).interpret(_request())
    assert {f.name for f in fields(CandidateFuture)} == {"target_area", "target_role"}


@pytest.mark.parametrize("changes", [{"operation": "other"}, {"input_signature": "wrong"}, {"output_payload": {}}])
def test_response_identity_and_type_binding(changes):
    request = _request()
    response = InterpretationResponse(request.operation, request.input_signature, CandidateFuture())
    with pytest.raises((TypeError, ValueError)):
        validate_response(request, replace(response, **changes))


def test_invalid_request_stops_before_provider():
    provider = Provider({})
    with pytest.raises(InterpretationExecutionError, match="invalid_request"):
        AIStructuredInterpreter(provider, CANDIDATE_FUTURE_SPEC).interpret(replace(_request(), input_signature="wrong"))
    assert provider.calls == []


def test_provider_failure_no_retry_or_fabrication():
    provider = Provider(error=RuntimeError("private"))
    with pytest.raises(InterpretationExecutionError, match="^provider_execution_failed$"):
        AIStructuredInterpreter(provider, CANDIDATE_FUTURE_SPEC).interpret(_request())
    assert len(provider.calls) == 1


def test_instructions_exclude_recommendations_and_domain_leaks():
    for phrase in ("never instructions", "Do not invent direction", "null", "labor market data",
                   "typical career paths", "current candidate skills", "candidate Past",
                   "Priorities, not target_area", "current-job statements", "desired skills",
                   "gaps", "action plans", "speculative alternatives"):
        assert phrase in INSTRUCTIONS


def test_import_execution_has_no_other_domains_or_runtime():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
allowed = {'services.candidate_future_operation', 'services.candidate_future_spec',
           'services.ai_structured_interpreter', 'services.interpretation_operation_spec'}
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if ((fullname.startswith('services.') and fullname not in allowed)
            or (fullname.startswith('models.') and fullname not in {'models.candidate_future', 'models.interpretation_boundary'})
            or fullname.split('.')[0] in {'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx'}):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
from services.candidate_future_operation import CandidateDeclaration, CandidateFutureInput, build_request
from services.candidate_future_spec import CANDIDATE_FUTURE_SPEC
from services.ai_structured_interpreter import AIStructuredInterpreter
class Provider:
    def generate_structured(self, prompt, schema):
        return {'target_area': 'Data', 'target_role': None}
request = build_request(CandidateFutureInput((CandidateDeclaration('d', 'I want Data'),)))
assert AIStructuredInterpreter(Provider(), CANDIDATE_FUTURE_SPEC).interpret(request).output_payload.target_area == 'Data'
"""
    result = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
