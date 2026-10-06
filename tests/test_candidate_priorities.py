from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_priorities import CandidatePriorities, Priority, PriorityEffect


def _priority(**changes):
    values = dict(
        id="priority-1", subject="compensation", operator="less_than",
        value=40000, effect=PriorityEffect.EXCLUDE,
    )
    return Priority(**(values | changes))


def test_identity_is_supplied_and_independent_of_rule_content():
    rule = _priority()
    assert replace(rule, value=45000).id == rule.id == "priority-1"
    assert replace(rule, id="priority-2").id != rule.id
    assert [field.name for field in fields(Priority)] == [
        "id", "subject", "operator", "value", "effect",
    ]


def test_effects_are_exactly_the_three_declared_semantics():
    assert PriorityEffect.__members__ == {
        "EXCLUDE": PriorityEffect.EXCLUDE,
        "DEPRIORITIZE": PriorityEffect.DEPRIORITIZE,
        "PREFER": PriorityEffect.PREFER,
    }


@pytest.mark.parametrize("subject, operator, value, effect", [
    ("compensation", "less_than", 40000, PriorityEffect.EXCLUDE),
    ("area", "equals", "Fraud", PriorityEffect.EXCLUDE),
    ("work_mode", "equals", "Remote", PriorityEffect.PREFER),
    ("contract_type", "equals", "Temporary", PriorityEffect.DEPRIORITIZE),
])
def test_structured_examples(subject, operator, value, effect):
    rule = Priority("rule", subject, operator, value, effect)
    assert (rule.subject, rule.operator, rule.value, rule.effect) == (
        subject, operator, value, effect,
    )


def test_same_subject_can_have_multiple_independent_rules():
    rules = CandidatePriorities((
        _priority(),
        _priority(id="currency-rule", operator="currency_equals", value="EUR"),
    ))
    assert len(rules.priorities) == 2
    assert {rule.subject for rule in rules.priorities} == {"compensation"}


@pytest.mark.parametrize("second", [_priority(), _priority(subject="area", value="Fraud")])
def test_duplicate_ids_rejected_even_with_different_content(second):
    with pytest.raises(ValueError, match="Duplicate"):
        CandidatePriorities((_priority(), second))


@pytest.mark.parametrize("field", ["id", "subject", "operator"])
@pytest.mark.parametrize("invalid", ["", "  ", "\t\n", None, 1, False])
def test_identity_and_rule_identifiers_must_be_nonblank_strings(field, invalid):
    with pytest.raises(ValueError):
        _priority(**{field: invalid})


def test_empty_priorities_are_valid():
    assert CandidatePriorities().priorities == ()


def test_immutable_value_collection():
    rule = _priority()
    priorities = CandidatePriorities((rule,))
    assert priorities == CandidatePriorities((_priority(),))
    assert hash(priorities) == hash(CandidatePriorities((_priority(),)))
    for field in fields(rule):
        with pytest.raises(FrozenInstanceError):
            setattr(rule, field.name, None)
    with pytest.raises(FrozenInstanceError):
        priorities.priorities = ()


@pytest.mark.parametrize("invalid", [[], [_priority()], ("rule",), (None,)])
def test_only_tuple_of_priority_values_accepted(invalid):
    with pytest.raises(TypeError):
        CandidatePriorities(invalid)


@pytest.mark.parametrize("value", [" Remote ", "", 40000, 40000.5, True, False, 0])
def test_scalar_values_preserved_without_coercion(value):
    rule = _priority(value=value)
    assert rule.value == value
    assert type(rule.value) is type(value)


@pytest.mark.parametrize("value", [None, [], {}, set(), (1,), object()])
def test_non_scalar_values_rejected(value):
    with pytest.raises(TypeError):
        _priority(value=value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_rejected(value):
    with pytest.raises(ValueError):
        _priority(value=value)


@pytest.mark.parametrize("effect", ["exclude", "EXCLUDE", None, 0])
def test_effect_must_be_closed_enum(effect):
    with pytest.raises(TypeError):
        _priority(effect=effect)


def test_identifiers_are_extensible_and_not_normalized():
    rule = _priority(id=" ID-1 ", subject="new_subject", operator="new_operator")
    assert (rule.id, rule.subject, rule.operator) == (" ID-1 ", "new_subject", "new_operator")


def test_no_execution_or_other_profile_branches_in_contract():
    assert [field.name for field in fields(CandidatePriorities)] == ["priorities"]
    for model in (Priority, CandidatePriorities):
        assert not [name for name, value in vars(model).items() if not name.startswith("_") and callable(value)]
    for field in ("target_role", "skills", "gaps", "plans", "experiences", "job_profile"):
        with pytest.raises(TypeError):
            CandidatePriorities(**{field: ()})


def test_import_and_use_are_independent_of_domains_and_infrastructure():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
class ForbidDependencies:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith('models.') and fullname != 'models.candidate_priorities') or fullname.split('.')[0] in {
            'services', 'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx',
        }:
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, ForbidDependencies())
from models.candidate_priorities import CandidatePriorities, Priority, PriorityEffect
rule = Priority('id', 'work_mode', 'equals', 'Remote', PriorityEffect.PREFER)
assert CandidatePriorities((rule,)).priorities == (rule,)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
