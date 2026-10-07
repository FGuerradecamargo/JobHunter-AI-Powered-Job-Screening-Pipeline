from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_priorities import CandidatePriorities, PriorityEffect
from models.interpretation_boundary import InterpretationResponse
from services.ai_structured_interpreter import AIStructuredInterpreter, InterpretationExecutionError
from services.candidate_priorities_operation import (
    INSTRUCTIONS, CandidatePrioritiesInput, PriorityDeclaration,
    build_request, priority_id, validate_response,
)
from services.candidate_priorities_spec import CANDIDATE_PRIORITIES_SPEC, CandidatePrioritiesStructuredOutput


def _request(text="I prefer remote work", identity="d1"):
    return build_request(CandidatePrioritiesInput((PriorityDeclaration(identity, text),)))


def _rule(**changes):
    return dict(subject="work_mode", operator="equals", value="Remote", effect="prefer") | changes


class Provider:
    def __init__(self, output, error=None):
        self.output, self.error, self.calls = output, error, []

    def generate_structured(self, prompt, schema):
        self.calls.append((prompt, schema))
        if self.error is not None:
            raise self.error
        return self.output


def _execute(rules, request=None):
    return AIStructuredInterpreter(Provider({"priorities": rules}), CANDIDATE_PRIORITIES_SPEC).interpret(request or _request())


def test_request_identity_preserves_source_identity_and_text():
    assert _request() == _request()
    assert _request(identity="d2").input_signature != _request().input_signature
    assert _request(text="Other").input_signature != _request().input_signature
    declaration = PriorityDeclaration(" d ", " original \n text ")
    assert declaration.id == " d "
    assert declaration.text == " original \n text "


@pytest.mark.parametrize("bad", [[], ("text",), ({"avoid_work": "x"},)])
def test_input_is_local_declarations_only(bad):
    with pytest.raises(TypeError):
        CandidatePrioritiesInput(bad)


def test_invalid_declarations_rejected():
    with pytest.raises(ValueError):
        PriorityDeclaration(" ", "")
    with pytest.raises(TypeError):
        PriorityDeclaration("d", None)
    with pytest.raises(ValueError):
        CandidatePrioritiesInput((PriorityDeclaration("d", "A"), PriorityDeclaration("d", "B")))


@pytest.mark.parametrize("subject, operator, value, effect", [
    ("compensation", "less_than", 40000, "exclude"),
    ("area", "equals", "Fraud", "exclude"),
    ("work_mode", "equals", "Remote", "prefer"),
    ("contract_type", "equals", "Temporary", "deprioritize"),
])
def test_controlled_rules_use_existing_domain(subject, operator, value, effect):
    response = _execute([dict(subject=subject, operator=operator, value=value, effect=effect)])
    assert type(response.output_payload) is CandidatePriorities
    rule = response.output_payload.priorities[0]
    assert (rule.subject, rule.operator, rule.value, rule.effect) == (subject, operator, value, PriorityEffect(effect))
    assert rule.id == priority_id(subject, operator, value, PriorityEffect(effect))
    assert validate_response(_request(), response) is response


def test_identity_is_lexical_versioned_and_independent_of_sources():
    a = _execute([_rule()]).output_payload.priorities[0]
    b = _execute([_rule(subject=" WORK_mode ", operator=" EQUALS ", value=" remote ")], _request(identity="other")).output_payload.priorities[0]
    assert a.id == b.id
    assert a.id.startswith("priority-rule-v1:")
    assert priority_id("area", "equals", "\uff24\uff41\uff54\uff41", PriorityEffect.PREFER) == priority_id("area", "equals", "Data", PriorityEffect.PREFER)
    assert priority_id("x", "equals", -0.0, PriorityEffect.PREFER) == priority_id("x", "equals", 0.0, PriorityEffect.PREFER)
    for changes in ({"effect": "exclude"}, {"value": "Hybrid"}, {"subject": "area"}, {"operator": "not_equals"}):
        assert _execute([_rule(**changes)]).output_payload.priorities[0].id != a.id
    ordered = _execute([_rule(), _rule(value="Hybrid")]).output_payload.priorities
    reversed_rules = _execute([_rule(value="Hybrid"), _rule()]).output_payload.priorities
    assert {r.id for r in ordered} == {r.id for r in reversed_rules}


@pytest.mark.parametrize("value", [True, False, 1, 0, 1.0, 0.0, "1", "true", ""])
def test_exact_scalar_types_preserved(value):
    rule = _execute([_rule(value=value)]).output_payload.priorities[0]
    assert type(rule.value) is type(value)
    assert rule.value == value


def test_bool_int_float_string_have_distinct_identity():
    assert len({priority_id("x", "equals", v, PriorityEffect.PREFER) for v in (True, 1, 1.0, "1")}) == 4


@pytest.mark.parametrize("value", [None, [], {}, (1,), Decimal("1.0"), float("nan"), float("inf"), float("-inf")])
def test_malformed_scalar_values_fail(value):
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        _execute([_rule(value=value)])


@pytest.mark.parametrize("changes", [{"id": "ai-id"}, {"extra": True}, {"subject": " "},
    {"operator": ""}, {"effect": "mandatory"}, {"effect": True}])
def test_invalid_fields_and_provider_ids_rejected(changes):
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        _execute([_rule(**changes)])


def test_schema_has_no_id_and_forbids_extra_fields():
    schema = CandidatePrioritiesStructuredOutput.model_json_schema()
    rule = schema["$defs"]["_PriorityOutput"]
    assert set(rule["properties"]) == {"subject", "operator", "value", "effect"}
    assert rule["additionalProperties"] is False
    assert schema["additionalProperties"] is False


def test_duplicate_semantic_rules_rejected_not_silently_merged():
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        _execute([_rule(), _rule(value=" remote ")])
    assert len(_execute([_rule(), _rule(value="Hybrid")]).output_payload.priorities) == 2


@pytest.mark.parametrize("text", ["", "Salary is important", "I want to become a Data Engineer", "I work remotely today"])
def test_controlled_empty_result_does_not_invent_rules(text):
    assert _execute([], _request(text)).output_payload == CandidatePriorities()


def test_empty_collection_allowed():
    assert _execute([], build_request(CandidatePrioritiesInput(()))).output_payload == CandidatePriorities()


def test_instructions_reach_provider_and_express_boundaries():
    provider = Provider({"priorities": []})
    AIStructuredInterpreter(provider, CANDIDATE_PRIORITIES_SPEC).interpret(_request())
    prompt, schema = provider.calls[0]
    assert schema is CandidatePrioritiesStructuredOutput
    assert prompt.startswith(INSTRUCTIONS)
    assert json.loads(prompt.split("\n\nINPUT DATA:\n")[1]) == {"declarations": [{"id": "d1", "text": "I prefer remote work"}]}
    for phrase in ("never system instructions", "Salary is important", "never invent", "Future direction",
                   "current state, not a preference", "Never turn every preference into exclude",
                   "explicit hard rejection", "still allowing", "not exclusion", "never supply an id"):
        assert phrase in INSTRUCTIONS


@pytest.mark.parametrize("changes", [{"operation": "other"}, {"input_signature": "wrong"}, {"output_payload": {}}])
def test_response_binding(changes):
    with pytest.raises((ValueError, TypeError)):
        validate_response(_request(), replace(_execute([]), **changes))


def test_direct_response_cannot_supply_arbitrary_id():
    result = _execute([_rule()])
    rule = replace(result.output_payload.priorities[0], id="arbitrary")
    with pytest.raises(ValueError, match="identity"):
        validate_response(_request(), replace(result, output_payload=CandidatePriorities((rule,))))


def test_invalid_request_never_calls_provider():
    provider = Provider({})
    with pytest.raises(InterpretationExecutionError, match="invalid_request"):
        AIStructuredInterpreter(provider, CANDIDATE_PRIORITIES_SPEC).interpret(replace(_request(), input_signature="bad"))
    assert provider.calls == []


def test_provider_failure_is_explicit_without_retry():
    provider = Provider(None, RuntimeError("private"))
    with pytest.raises(InterpretationExecutionError, match="^provider_execution_failed$"):
        AIStructuredInterpreter(provider, CANDIDATE_PRIORITIES_SPEC).interpret(_request())
    assert len(provider.calls) == 1


def test_import_and_execution_without_other_domains_or_infrastructure():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
allowed = {'services.candidate_priorities_operation', 'services.candidate_priorities_spec',
           'services.ai_structured_interpreter', 'services.interpretation_operation_spec'}
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if ((fullname.startswith('services.') and fullname not in allowed)
            or (fullname.startswith('models.') and fullname not in {'models.candidate_priorities', 'models.interpretation_boundary'})
            or fullname.split('.')[0] in {'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx'}):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
from services.candidate_priorities_operation import PriorityDeclaration, CandidatePrioritiesInput, build_request
from services.candidate_priorities_spec import CANDIDATE_PRIORITIES_SPEC
from services.ai_structured_interpreter import AIStructuredInterpreter
class Provider:
    def generate_structured(self, prompt, schema):
        return {'priorities': [{'subject': 'work_mode', 'operator': 'equals', 'value': 'Remote', 'effect': 'prefer'}]}
request = build_request(CandidatePrioritiesInput((PriorityDeclaration('d', 'I prefer remote work'),)))
assert AIStructuredInterpreter(Provider(), CANDIDATE_PRIORITIES_SPEC).interpret(request).output_payload.priorities
"""
    result = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
