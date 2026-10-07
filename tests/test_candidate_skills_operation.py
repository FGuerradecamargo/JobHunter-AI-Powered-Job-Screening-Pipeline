from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_past import CandidateInput, ProfessionalFact
from models.candidate_present import CandidateSkill, ProfessionalFactRef
from models.professional_ontology import Skill, SkillLevel
from models.interpretation_boundary import InterpretationResponse
from services.ai_structured_interpreter import AIStructuredInterpreter, InterpretationExecutionError
from services.candidate_skills_operation import (
    INSTRUCTIONS, CandidateSkillsInput, CandidateSkillsOutput, build_request,
    normalized_skill_id, validate_response,
)
from services.candidate_skills_spec import CANDIDATE_SKILLS_SPEC, CandidateSkillsStructuredOutput


def _request():
    return build_request(CandidateSkillsInput((ProfessionalFact("f1", "Investigated account history.", "i1"),)))


def _raw(**changes):
    item = dict(name="Case Investigation", category="Investigation", subcategory=None,
                level="unknown", evidence_refs=["f1"])
    return {"skills": [item | changes]}


class Provider:
    def __init__(self, raw=None, error=None):
        self.raw, self.error, self.calls = raw, error, []

    def generate_structured(self, prompt, schema):
        self.calls.append((prompt, schema))
        if self.error:
            raise self.error
        return self.raw


def _execute(raw, request=None):
    return AIStructuredInterpreter(Provider(raw), CANDIDATE_SKILLS_SPEC).interpret(request or _request())


def test_request_signature_deterministic_and_content_sensitive():
    request = _request()
    assert request == _request()
    changed = build_request(CandidateSkillsInput((ProfessionalFact("f1", "Different activity.", "i1"),)))
    assert changed.input_signature != request.input_signature


@pytest.mark.parametrize("facts", [[], (CandidateInput("i", "RAW"),), ("text",),
    (ProfessionalFact("f", "A", "i"), ProfessionalFact("f", "B", "i")),
    (ProfessionalFact("f", "A", "i"), ProfessionalFact("g", "B", "f")),
])
def test_input_rejects_raw_duplicate_and_fact_chains(facts):
    with pytest.raises((TypeError, ValueError)):
        CandidateSkillsInput(facts)


def test_typed_fact_only_execution_and_instructions():
    provider = Provider(_raw())
    request = _request()
    response = AIStructuredInterpreter(provider, CANDIDATE_SKILLS_SPEC).interpret(request)
    assert (response.operation, response.input_signature) == (request.operation, request.input_signature)
    assert validate_response(request, response) is response
    skill = response.output_payload.skills[0]
    assert type(skill) is CandidateSkill
    assert type(skill.skill) is Skill
    assert skill.level is SkillLevel.UNKNOWN
    assert skill.evidence_refs == (ProfessionalFactRef("f1"),)
    assert provider.calls[0][1] is CandidateSkillsStructuredOutput
    assert provider.calls[0][0].startswith(INSTRUCTIONS)
    assert "Investigated account history." in provider.calls[0][0]


def test_identity_normalizes_case_whitespace_unicode_not_punctuation_or_synonyms():
    assert normalized_skill_id("  Case   Investigation ") == normalized_skill_id("case investigation")
    assert normalized_skill_id("SQL") == normalized_skill_id("\uff33\uff31\uff2c")
    assert normalized_skill_id("C++") != normalized_skill_id("C")
    assert normalized_skill_id("Case Investigation") != normalized_skill_id("Fraud Investigation")
    a = _execute(_raw()).output_payload.skills[0]
    b = _execute(_raw(category="Other", level="basic")).output_payload.skills[0]
    assert a.skill.id == b.skill.id


@pytest.mark.parametrize("level", list(SkillLevel))
def test_all_semantic_levels_roundtrip(level):
    assert _execute(_raw(level=level.value)).output_payload.skills[0].level is level
    with pytest.raises(TypeError):
        level < SkillLevel.EXPERT


@pytest.mark.parametrize("changes", [
    {"evidence_refs": []}, {"evidence_refs": ["i1"]}, {"evidence_refs": ["unknown"]},
    {"evidence_refs": ["f1", "f1"]}, {"evidence_refs": [1]}, {"evidence_refs": [""]},
    {"level": 3}, {"level": "master"}, {"name": " "}, {"category": ""},
    {"subcategory": " "}, {"id": "fabricated"},
])
def test_invalid_provider_skill_fails(changes):
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        _execute(_raw(**changes))


def test_duplicate_normalized_skill_ids_fail():
    raw = _raw()
    raw["skills"].append(_raw(name=" case INVESTIGATION ")["skills"][0])
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        _execute(raw)


def test_multiple_facts_per_skill_and_multiple_skills_per_fact():
    request = build_request(CandidateSkillsInput((
        ProfessionalFact("f1", "Investigated account history.", "i1"),
        ProfessionalFact("f2", "Wrote investigation reports.", "i2"),
    )))
    raw = _raw(evidence_refs=["f1", "f2"])
    raw["skills"].append(_raw(name="Report Writing", evidence_refs=["f2"])["skills"][0])
    assert len(_execute(raw, request).output_payload.skills) == 2


@pytest.mark.parametrize("changes", [{"operation": "other"}, {"input_signature": "wrong"}])
def test_response_binding_checked(changes):
    response = _execute(_raw())
    with pytest.raises(ValueError):
        validate_response(_request(), replace(response, **changes))


def test_direct_output_and_identity_validation():
    with pytest.raises(TypeError):
        CandidateSkillsOutput(("not a skill",))
    skill = _execute(_raw()).output_payload.skills[0]
    with pytest.raises(ValueError):
        CandidateSkillsOutput((skill, skill))
    invalid = replace(skill, skill=replace(skill.skill, id="invented"))
    request = _request()
    with pytest.raises(ValueError, match="identity"):
        validate_response(request, InterpretationResponse(request.operation, request.input_signature,
                                                         CandidateSkillsOutput((invalid,))))


def test_empty_facts_do_not_require_raw_or_produce_skills():
    request = build_request(CandidateSkillsInput(()))
    assert _execute({"skills": []}, request).output_payload.skills == ()
    with pytest.raises(InterpretationExecutionError, match="invalid_output"):
        _execute(_raw(), request)


def test_provider_failure_explicit_no_retry():
    provider = Provider(error=RuntimeError("private"))
    with pytest.raises(InterpretationExecutionError, match="^provider_execution_failed$"):
        AIStructuredInterpreter(provider, CANDIDATE_SKILLS_SPEC).interpret(_request())
    assert len(provider.calls) == 1


def test_stale_request_rejected_before_provider():
    provider = Provider(_raw())
    with pytest.raises(InterpretationExecutionError, match="invalid_request"):
        AIStructuredInterpreter(provider, CANDIDATE_SKILLS_SPEC).interpret(replace(_request(), input_signature="bad"))
    assert provider.calls == []


def test_instructions_preserve_semantic_limits():
    for phrase in ("role/title", "employer/company", "industry", "typical-role", "expertise",
                   "metrics", "seniority", "unknown", "not a", "negative capability"):
        assert phrase in INSTRUCTIONS


def test_import_and_execution_do_not_load_raw_or_construct_aggregates():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
allowed = {'services.ai_structured_interpreter', 'services.interpretation_operation_spec',
           'services.candidate_skills_operation', 'services.candidate_skills_spec'}
models = {'models.candidate_past', 'models.candidate_present', 'models.professional_ontology',
          'models.interpretation_boundary'}
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if ((fullname.startswith('services.') and fullname not in allowed)
            or (fullname.startswith('models.') and fullname not in models)
            or fullname.split('.')[0] in {'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx'}):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
import models.candidate_past as past
import models.candidate_present as present
def forbidden(*args, **kwargs):
    raise AssertionError('Aggregate or RAW construction')
past.CandidateInput = past.CandidatePast = present.CandidatePresent = forbidden
from services.candidate_skills_operation import CandidateSkillsInput, build_request
from services.candidate_skills_spec import CANDIDATE_SKILLS_SPEC
from services.ai_structured_interpreter import AIStructuredInterpreter
class Provider:
    def generate_structured(self, prompt, schema):
        return {'skills': [{'name': 'SQL', 'category': 'Data', 'subcategory': None,
                            'level': 'unknown', 'evidence_refs': ['f']}]}
request = build_request(CandidateSkillsInput((past.ProfessionalFact('f', 'Used SQL.', 'i'),)))
assert AIStructuredInterpreter(Provider(), CANDIDATE_SKILLS_SPEC).interpret(request).output_payload.skills
"""
    result = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
