from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_past import CandidateInput, ProfessionalFact
from models.interpretation_boundary import InterpretationRequest, InterpretationResponse, StructuredInterpreter
from services.professional_facts_operation import (
    INSTRUCTIONS, OPERATION, ProfessionalFactsInput, ProfessionalFactsOutput, build_request, validate_response,
)


class FixtureOperation:
    """Fixed output double; exercises the canonical verb, not semantic AI."""
    def __init__(self, facts):
        self.output = ProfessionalFactsOutput(facts)

    def interpret(self, request: InterpretationRequest[ProfessionalFactsInput]) -> InterpretationResponse[ProfessionalFactsOutput]:
        return validate_response(request, InterpretationResponse(request.operation, request.input_signature, self.output))


def run(inputs, facts):
    interpreter: StructuredInterpreter[
        InterpretationRequest[ProfessionalFactsInput], InterpretationResponse[ProfessionalFactsOutput]
    ] = FixtureOperation(facts)
    return interpreter.interpret(build_request(ProfessionalFactsInput(inputs)))


@pytest.mark.parametrize("statements", [
    ("Answered customers by phone",),
    ("Answered customers by phone", "Investigated account history", "Consulted policies", "Decided resolution"),
])
def test_one_original_input_supports_one_or_multiple_facts(statements):
    source = CandidateInput("input-1", "  I answered customers by phone, investigated account history, consulted policies and decided resolution.  ")
    facts = tuple(ProfessionalFact(f"fact-{i}", text, source.id) for i, text in enumerate(statements))
    result = run((source,), facts)
    assert result.operation == OPERATION
    assert result.output_payload.facts == facts
    assert all(type(fact) is ProfessionalFact and fact.candidate_input_id == source.id for fact in facts)
    assert build_request(ProfessionalFactsInput((source,))).input_payload.inputs[0] is source
    assert run((source,), facts) == result


def test_multiple_inputs_keep_explicit_separate_provenance():
    inputs = (CandidateInput("a", "I investigated history."), CandidateInput("b", "I consulted policies."))
    facts = (ProfessionalFact("f1", "Investigated history", "a"), ProfessionalFact("f2", "Consulted policies", "b"))
    assert [(f.statement, f.candidate_input_id) for f in run(inputs, facts).output_payload.facts] == [
        ("Investigated history", "a"), ("Consulted policies", "b"),
    ]


@pytest.mark.parametrize("reference", ["unknown", "f1"])
def test_unknown_refs_and_fact_to_fact_chains_fail(reference):
    with pytest.raises(ValueError, match="supplied original"):
        run((CandidateInput("input", "Original"),), (
            ProfessionalFact("f1", "First", "input"), ProfessionalFact("f2", "Second", reference),
        ))


def test_duplicate_ids_and_source_identity_collision_fail():
    fact = ProfessionalFact("f", "Statement", "a")
    with pytest.raises(ValueError, match="Duplicate fact"):
        ProfessionalFactsOutput((fact, fact))
    with pytest.raises(ValueError, match="distinct"):
        run((CandidateInput("a", "Original"), CandidateInput("b", "Other")), (ProfessionalFact("b", "Statement", "a"),))
    with pytest.raises(ValueError, match="Duplicate candidate"):
        ProfessionalFactsInput((CandidateInput("a", "One"), CandidateInput("a", "Two")))


@pytest.mark.parametrize("field", ["id", "statement", "candidate_input_id"])
@pytest.mark.parametrize("blank", ["", " \t"])
def test_fact_contract_rejects_blank_values(field, blank):
    values = dict(id="fact", statement="Statement", candidate_input_id="input")
    values[field] = blank
    with pytest.raises(ValueError):
        ProfessionalFact(**values)


def test_interpreted_fact_cannot_be_supplied_as_original_input():
    with pytest.raises(TypeError):
        ProfessionalFactsInput((ProfessionalFact("fact", "Statement", "input"),))
    with pytest.raises(TypeError):
        ProfessionalFactsOutput((CandidateInput("input", "Text"),))


def test_result_is_bound_to_exact_operation_and_input():
    request = build_request(ProfessionalFactsInput((CandidateInput("input", "Original"),)))
    response = InterpretationResponse(OPERATION, request.input_signature, ProfessionalFactsOutput(()))
    assert validate_response(request, response) is response
    for invalid in (replace(response, operation="other.v1"), replace(response, input_signature="other")):
        with pytest.raises(ValueError):
            validate_response(request, invalid)
    changed = replace(request, input_payload=ProfessionalFactsInput((CandidateInput("input", "Changed"),)))
    with pytest.raises(ValueError):
        validate_response(changed, response)
    with pytest.raises(TypeError):
        validate_response(request, replace(response, output_payload={"skills": []}))


def test_contracts_are_small_immutable_and_instructions_forbid_semantic_invention():
    payload = ProfessionalFactsInput((CandidateInput("a", "Text"),))
    assert [f.name for f in fields(payload)] == ["inputs"]
    assert [f.name for f in fields(ProfessionalFactsOutput)] == ["facts"]
    with pytest.raises(FrozenInstanceError):
        payload.inputs = ()
    with pytest.raises(TypeError):
        ProfessionalFactsInput(list(payload.inputs))
    with pytest.raises(ValueError):
        ProfessionalFactsInput(())
    assert "Do not turn facts\ninto skills" in INSTRUCTIONS
    assert "Never use an interpretation as new source material" in INSTRUCTIONS
    assert "external context" in INSTRUCTIONS


def test_operation_import_is_isolated_and_constructs_no_profile_or_past():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
class ForbidDependencies:
    def find_spec(self, fullname, path=None, target=None):
        if ((fullname.startswith('services.') and fullname != 'services.professional_facts_operation')
            or (fullname.startswith('models.') and fullname not in {'models.candidate_past', 'models.interpretation_boundary'})
            or fullname.split('.')[0] in {'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx'}):
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, ForbidDependencies())
from services.professional_facts_operation import *
import models.candidate_past as past
def forbidden(*args, **kwargs):
    raise AssertionError('Unexpected domain construction')
past.CandidatePast = past.Experience = past.Education = forbidden
request = build_request(ProfessionalFactsInput((CandidateInput('a', 'Original'),)))
result = InterpretationResponse(OPERATION, request.input_signature, ProfessionalFactsOutput((ProfessionalFact('f', 'Original', 'a'),)))
assert validate_response(request, result) is result
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
