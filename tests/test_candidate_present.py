from dataclasses import FrozenInstanceError, asdict, fields, replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_past import CandidateInput, Experience, ProfessionalFact
from models.candidate_present import CandidatePresent, CandidateSkill, ProfessionalFactRef
from models.professional_ontology import Skill, SkillLevel


def assessed(level=SkillLevel.INDEPENDENT, refs=(ProfessionalFactRef("fact-1"),)):
    return CandidateSkill(Skill("python", "Python", "Technical"), level, refs)


def test_present_encapsulates_canonical_skill_and_shared_level():
    item = assessed()
    present = CandidatePresent((item,))
    assert present.skills[0] is item
    assert type(item.skill) is Skill
    assert item.level is SkillLevel.INDEPENDENT
    assert replace(item, level=SkillLevel.ADVANCED).skill.id == item.skill.id
    assert hash(present) == hash(CandidatePresent((assessed(),)))
    payload = asdict(item)
    payload["level"] = item.level.value
    assert json.loads(json.dumps(payload))["evidence_refs"] == [{"fact_id": "fact-1"}]


@pytest.mark.parametrize("count", [1, 2])
def test_references_can_trace_to_past_facts_and_original_input(count):
    source = CandidateInput("input", "I wrote Python scripts and tested them.")
    facts = tuple(ProfessionalFact(f"fact-{i}", statement, source.id) for i, statement in enumerate(
        ("Wrote Python scripts", "Tested scripts")[:count], start=1,
    ))
    past = Experience("exp", "Company", "Role", inputs=(source,), facts=facts)
    item = assessed(refs=tuple(ProfessionalFactRef(fact.id) for fact in facts))
    for ref in item.evidence_refs:
        fact = next(fact for fact in past.facts if fact.id == ref.fact_id)
        assert fact.candidate_input_id == past.inputs[0].id
    assert {field.name for field in fields(item)} == {"skill", "level", "evidence_refs"}
    assert {field.name for field in fields(ProfessionalFactRef)} == {"fact_id"}
    assert {field.name for field in fields(CandidatePresent)} == {"skills"}


def test_unknown_is_an_identified_skill_not_absence_or_zero():
    present = CandidatePresent((assessed(SkillLevel.UNKNOWN),))
    assert present != CandidatePresent()
    assert present.skills[0].skill.id == "python"
    assert present.skills[0].level is SkillLevel.UNKNOWN
    with pytest.raises(TypeError):
        assessed(0)
    with pytest.raises(TypeError):
        assessed("unknown")


@pytest.mark.parametrize("other", [
    assessed(), assessed(SkillLevel.UNKNOWN),
    replace(assessed(), skill=Skill("python", "Renamed Python", "Programming")),
])
def test_duplicate_identity_is_rejected_regardless_of_level_or_label(other):
    with pytest.raises(ValueError, match="Duplicate candidate skill"):
        CandidatePresent((assessed(), other))


@pytest.mark.parametrize("invalid", [
    "fact-1", CandidateInput("input", "Text"), ProfessionalFact("fact", "Statement", "input"),
    Experience("exp", "Company", "Role"), assessed(), CandidatePresent((assessed(),)),
])
def test_evidence_accepts_only_fact_references_not_objects_or_present_interpretations(invalid):
    with pytest.raises(TypeError):
        assessed(refs=(invalid,))
    with pytest.raises(ValueError):
        ProfessionalFactRef(invalid if not isinstance(invalid, str) else "")


def test_evidence_requires_nonblank_unique_references():
    for invalid in (None, 0, "", "   "):
        with pytest.raises(ValueError):
            ProfessionalFactRef(invalid)
    with pytest.raises(ValueError):
        assessed(refs=())
    with pytest.raises(ValueError):
        assessed(refs=(ProfessionalFactRef("fact"), ProfessionalFactRef("fact")))


def test_mutable_collections_and_parallel_skill_definitions_are_rejected():
    with pytest.raises(TypeError):
        CandidatePresent([assessed()])
    with pytest.raises(TypeError):
        assessed(refs=[ProfessionalFactRef("fact")])
    with pytest.raises(TypeError):
        CandidateSkill({"id": "python"}, SkillLevel.BASIC, (ProfessionalFactRef("fact"),))


@pytest.mark.parametrize("value", [ProfessionalFactRef("fact"), assessed(), CandidatePresent((assessed(),))])
def test_values_are_immutable(value):
    with pytest.raises(FrozenInstanceError):
        setattr(value, fields(value)[0].name, "Changed")


def test_import_and_usage_are_independent_of_past_and_infrastructure():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
class ForbidInfrastructure:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'models.candidate_past' or fullname.split('.')[0] in {
            'services', 'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx',
        }:
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, ForbidInfrastructure())
from models.candidate_present import CandidatePresent, CandidateSkill, ProfessionalFactRef
from models.professional_ontology import Skill, SkillLevel
item = CandidateSkill(Skill('python', 'Python', 'Technical'), SkillLevel.UNKNOWN, (ProfessionalFactRef('fact'),))
assert CandidatePresent((item,)).skills[0] is item
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
