from dataclasses import FrozenInstanceError, asdict, fields, replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from models.professional_ontology import Skill, SkillLevel


def test_skill_is_an_immutable_serializable_value():
    skill = Skill("sql", "SQL", "Technical", "Query languages")
    assert [field.name for field in fields(skill)] == ["id", "name", "category", "subcategory"]
    assert Skill(**json.loads(json.dumps(asdict(skill)))) == skill
    assert hash(skill) == hash(Skill("sql", "SQL", "Technical", "Query languages"))
    assert replace(skill, name="Structured Query Language").id == skill.id
    with pytest.raises(FrozenInstanceError):
        skill.name = "Changed"
    assert Skill("communication", "Communication", "Professional").subcategory is None


@pytest.mark.parametrize("field", ["id", "name", "category", "subcategory"])
@pytest.mark.parametrize("value", ["", "   ", 0])
def test_skill_rejects_invalid_labels(field, value):
    values = dict(id="sql", name="SQL", category="Technical")
    values[field] = value
    with pytest.raises(ValueError):
        Skill(**values)


def test_levels_are_explicit_semantic_states_not_numeric_ranks():
    assert [level.name for level in SkillLevel] == [
        "UNKNOWN", "BASIC", "SUPPORTED", "INDEPENDENT", "ADVANCED", "EXPERT",
    ]
    for level in SkillLevel:
        assert SkillLevel(json.loads(json.dumps(level.value))) is level
    assert all(SkillLevel.UNKNOWN != level for level in SkillLevel if level is not SkillLevel.UNKNOWN)
    with pytest.raises(ValueError):
        SkillLevel(0)
    with pytest.raises(TypeError):
        SkillLevel.UNKNOWN < SkillLevel.BASIC
    with pytest.raises(TypeError):
        SkillLevel.BASIC < SkillLevel.SUPPORTED


def test_import_and_use_do_not_load_application_infrastructure():
    # Fresh interpreter avoids infrastructure imported by the suite's conftest.
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
class ForbidInfrastructure:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'services', 'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx',
        }:
            raise AssertionError('Unexpected infrastructure import: ' + fullname)
sys.meta_path.insert(0, ForbidInfrastructure())
from models.professional_ontology import Skill, SkillLevel
assert Skill('sql', 'SQL', 'Technical').id == 'sql'
assert SkillLevel.UNKNOWN.value == 'unknown'
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
