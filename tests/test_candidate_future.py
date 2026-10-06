from dataclasses import FrozenInstanceError, asdict, fields
import json
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_future import CandidateFuture


@pytest.mark.parametrize("area, role", [
    ("Data", "Data Engineer"), ("Data", None), (None, "Data Engineer"), (None, None),
])
def test_direction_fields_are_independently_optional(area, role):
    future = CandidateFuture(target_area=area, target_role=role)
    assert future.target_area == area
    assert future.target_role == role
    assert CandidateFuture(**json.loads(json.dumps(asdict(future)))) == future
    assert hash(future) == hash(CandidateFuture(area, role))


def test_empty_future_does_not_invent_direction():
    assert CandidateFuture() == CandidateFuture(None, None)


@pytest.mark.parametrize("field", ["target_area", "target_role"])
@pytest.mark.parametrize("invalid", ["", "   ", "\t\n", 0, False, [], {}])
def test_non_null_values_must_be_nonblank_strings(field, invalid):
    with pytest.raises(ValueError):
        CandidateFuture(**{field: invalid})


def test_values_are_preserved_without_normalization_or_inference():
    future = CandidateFuture("  DATA / Analytics  ", "Data\nEngineer (aspiring)")
    assert future.target_area == "  DATA / Analytics  "
    assert future.target_role == "Data\nEngineer (aspiring)"
    assert CandidateFuture(target_role=future.target_role).target_area is None
    assert CandidateFuture(target_area=future.target_area).target_role is None


@pytest.mark.parametrize("field", ["target_area", "target_role"])
def test_contract_is_immutable(field):
    future = CandidateFuture("Data", "Data Engineer")
    with pytest.raises(FrozenInstanceError):
        setattr(future, field, "Changed")


def test_future_contains_only_declared_area_and_role():
    assert [field.name for field in fields(CandidateFuture)] == ["target_area", "target_role"]
    with pytest.raises(TypeError):
        CandidateFuture(skills=("Python",))


def test_import_and_use_require_no_other_domains_or_infrastructure():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
class ForbidDependencies:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith('models.') and fullname != 'models.candidate_future') or fullname.split('.')[0] in {
            'services', 'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx',
        }:
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, ForbidDependencies())
from models.candidate_future import CandidateFuture
assert CandidateFuture(target_role='Data Engineer').target_area is None
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
