from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_past import CandidateInput, CandidatePast, Education, Experience, ProfessionalFact
from models.candidate_present import CandidatePresent, CandidateSkill, ProfessionalFactRef
from models.candidate_future import CandidateFuture
from models.candidate_priorities import CandidatePriorities, Priority, PriorityEffect
from models.candidate_profile_snapshot import CandidateProfileSnapshot
from models.professional_ontology import Skill, SkillLevel


def _snapshot(**changes):
    values = dict(
        candidate_id="candidate-1", version=1, past=CandidatePast(),
        present=CandidatePresent(), future=CandidateFuture(), priorities=CandidatePriorities(),
    )
    return CandidateProfileSnapshot(**(values | changes))


def test_identity_and_first_version_preserved():
    snapshot = _snapshot(candidate_id=" Candidate-1 ")
    assert snapshot.candidate_id == " Candidate-1 "
    assert snapshot.version == 1


@pytest.mark.parametrize("include_education", [False, True])
def test_skill_evidence_resolves_across_past_entities(include_education):
    first = Experience("e1", "Company", "Role", inputs=(CandidateInput("i1", "SQL"),),
                       facts=(ProfessionalFact("f1", "Used SQL", "i1"),))
    values = dict(inputs=(CandidateInput("i2", "More SQL"),), facts=(ProfessionalFact("f2", "Used SQL", "i2"),))
    second = Education("e2", "College", "Diploma", "Data", **values) if include_education else Experience("e2", "Other", "Role", **values)
    past = CandidatePast((first,), (second,)) if include_education else CandidatePast((first, second))
    skill = CandidateSkill(Skill("sql", "SQL", "Data"), SkillLevel.UNKNOWN,
                           (ProfessionalFactRef("f1"), ProfessionalFactRef("f2")))
    assert _snapshot(past=past, present=CandidatePresent((skill,))).present.skills == (skill,)
    assert _snapshot(past=past).present.skills == ()
    dangling = replace(skill, evidence_refs=(ProfessionalFactRef("f1"), ProfessionalFactRef("missing")))
    with pytest.raises(ValueError, match="resolve"):
        _snapshot(past=past, present=CandidatePresent((dangling,)))
    with pytest.raises(ValueError, match="resolve"):
        _snapshot(present=CandidatePresent((skill,)))


@pytest.mark.parametrize("version", [0, -1, 1.0, "1", True, False, None])
def test_only_positive_integer_versions_accepted(version):
    with pytest.raises(ValueError, match="positive integer"):
        _snapshot(version=version)


@pytest.mark.parametrize("candidate_id", ["", "  ", "\t\n", None, 1, False])
def test_nonblank_candidate_identity_required(candidate_id):
    with pytest.raises(ValueError, match="nonblank"):
        _snapshot(candidate_id=candidate_id)


def test_branches_are_composed_directly_and_can_be_traversed():
    original = CandidateInput("input-1", "I used SQL for reporting.")
    fact = ProfessionalFact("fact-1", "Used SQL for reporting.", original.id)
    past = CandidatePast(experiences=(Experience(
        "experience-1", "Example", "Analyst", inputs=(original,), facts=(fact,),
    ),))
    present = CandidatePresent((CandidateSkill(
        Skill("sql", "SQL", "Data"), SkillLevel.INDEPENDENT,
        (ProfessionalFactRef(fact.id),),
    ),))
    future = CandidateFuture("Data", "Data Engineer")
    priorities = CandidatePriorities((Priority(
        "priority-1", "work_mode", "equals", "Remote", PriorityEffect.PREFER,
    ),))
    snapshot = _snapshot(past=past, present=present, future=future, priorities=priorities)
    assert snapshot.past is past
    assert snapshot.present is present
    assert snapshot.future is future
    assert snapshot.priorities is priorities
    assert snapshot.past.experiences[0].facts[0] is fact
    assert snapshot.past.experiences[0].inputs[0] is original
    assert snapshot.present.skills[0].evidence_refs[0].fact_id == fact.id


@pytest.mark.parametrize("branch", ["past", "present", "future", "priorities"])
@pytest.mark.parametrize("invalid", [None, {}, (), "branch"])
def test_branch_contract_types_are_required(branch, invalid):
    with pytest.raises(TypeError):
        _snapshot(**{branch: invalid})


def test_branches_cannot_be_swapped():
    with pytest.raises(TypeError):
        _snapshot(past=CandidatePresent())


def test_empty_branches_do_not_invent_information():
    snapshot = _snapshot()
    assert snapshot.past == CandidatePast()
    assert snapshot.present.skills == ()
    assert snapshot.future.target_area is None
    assert snapshot.future.target_role is None
    assert snapshot.priorities.priorities == ()


def test_immutable_value_semantics():
    snapshot = _snapshot()
    assert snapshot == _snapshot()
    assert hash(snapshot) == hash(_snapshot())
    for field in fields(snapshot):
        with pytest.raises(FrozenInstanceError):
            setattr(snapshot, field.name, None)


def test_versions_coexist_without_mutating_previous_state():
    v1 = _snapshot()
    v2 = replace(v1, version=2, future=CandidateFuture(target_role="Data Engineer"))
    assert v1.candidate_id == v2.candidate_id
    assert (v1.version, v2.version) == (1, 2)
    assert v1.future.target_role is None
    assert v2.future.target_role == "Data Engineer"
    assert v2.past is v1.past
    assert v2.present is v1.present
    assert v2.priorities is v1.priorities
    assert len({v1, v2}) == 2


def test_root_has_only_identity_version_and_branches():
    assert [field.name for field in fields(CandidateProfileSnapshot)] == [
        "candidate_id", "version", "past", "present", "future", "priorities",
    ]
    assert not [
        name for name, value in vars(CandidateProfileSnapshot).items()
        if not name.startswith("_") and callable(value)
    ]
    snapshot = _snapshot()
    for name in (
        "skills", "experiences", "target_role", "salary_priority", "raw_source_signature",
        "memory_signature", "readiness", "update", "generate", "interpret", "save", "load",
    ):
        assert not hasattr(snapshot, name)


def test_legacy_snapshot_is_a_separate_unmodified_contract():
    from models.profile_interpretation import CandidateProfileSnapshot as LegacySnapshot

    assert LegacySnapshot is not CandidateProfileSnapshot
    assert "memory_signature" in {field.name for field in fields(LegacySnapshot)}
    assert not isinstance(_snapshot(), LegacySnapshot)


def test_import_and_read_require_only_closed_domain_contracts():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
allowed = {
    'models.candidate_profile_snapshot', 'models.candidate_past',
    'models.candidate_present', 'models.candidate_future',
    'models.candidate_priorities', 'models.professional_ontology',
}
class ForbidDependencies:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith('models.') and fullname not in allowed) or fullname.split('.')[0] in {
            'services', 'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx',
        }:
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, ForbidDependencies())
from models.candidate_profile_snapshot import CandidateProfileSnapshot
from models.candidate_past import CandidatePast
from models.candidate_present import CandidatePresent
from models.candidate_future import CandidateFuture
from models.candidate_priorities import CandidatePriorities
snapshot = CandidateProfileSnapshot(
    'candidate', 1, CandidatePast(), CandidatePresent(), CandidateFuture(), CandidatePriorities(),
)
assert snapshot.version == 1
assert snapshot.future.target_role is None
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
