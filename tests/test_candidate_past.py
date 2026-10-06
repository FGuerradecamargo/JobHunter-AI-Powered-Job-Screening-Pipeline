from dataclasses import FrozenInstanceError, asdict, fields, replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from models.candidate_past import (
    CandidateInput, CandidatePast, Certification, Education, Experience, ProfessionalFact,
)


def experience(**kwargs):
    return Experience("exp-1", "Example", "Support", **kwargs)


def education(**kwargs):
    return Education("edu-1", "College", "Diploma", "Computing", **kwargs)


def test_past_encapsulates_independent_entities_and_serializes():
    exp = experience(start_date="2020-01")
    edu = education(start_date="2018", end_date="2019", status="completed")
    cert = Certification("cert-1", "Credential", "Issuer", "2019-01", None, "active")
    past = CandidatePast((exp,), (edu,), (cert,))
    assert past.experiences[0] is exp
    assert past.education[0] is edu
    assert past.certifications[0] is cert
    assert exp.end_date is None
    assert replace(exp, role="Senior support").id == exp.id
    assert json.loads(json.dumps(asdict(past)))["experiences"][0]["company"] == "Example"
    assert CandidatePast() == CandidatePast()
    assert hash(past) == hash(CandidatePast((exp,), (edu,), (cert,)))


@pytest.mark.parametrize("parent", [experience, education])
def test_original_input_supports_multiple_facts_without_rewriting(parent):
    source = CandidateInput("input-1", "  I investigated history.\nI consulted policies.  ")
    facts = (
        ProfessionalFact("fact-1", "Investigated history", source.id),
        ProfessionalFact("fact-2", "Consulted policies", source.id),
    )
    entity = parent(inputs=(source,), facts=facts)
    assert entity.inputs[0].original_text == source.original_text
    assert all(fact.candidate_input_id == source.id for fact in entity.facts)
    assert [f.name for f in fields(ProfessionalFact)] == ["id", "statement", "candidate_input_id"]


@pytest.mark.parametrize("parent", [experience, education])
@pytest.mark.parametrize("source_id", ["missing", "fact-1"])
def test_missing_sources_and_interpretation_chains_are_rejected(parent, source_id):
    with pytest.raises(ValueError, match="original input"):
        parent(inputs=(CandidateInput("input-1", "Original"),), facts=(
            ProfessionalFact("fact-1", "First interpretation", "input-1"),
            ProfessionalFact("fact-2", "Second interpretation", source_id),
        ))


def test_reference_cannot_be_a_fact_object_or_self_reference():
    fact = ProfessionalFact("fact", "Statement", "input")
    with pytest.raises(ValueError):
        ProfessionalFact("other", "Statement", fact)
    with pytest.raises(ValueError):
        ProfessionalFact("fact", "Statement", "fact")
    with pytest.raises(TypeError):
        experience(inputs=(fact,))


@pytest.mark.parametrize("parent", [experience, education])
def test_provenance_is_local_and_identities_unambiguous(parent):
    source = CandidateInput("input", "Original")
    fact = ProfessionalFact("fact", "Statement", "input")
    with pytest.raises(ValueError, match="Duplicate"):
        parent(inputs=(source, source))
    with pytest.raises(ValueError, match="Duplicate"):
        parent(inputs=(source,), facts=(fact, fact))
    with pytest.raises(ValueError, match="distinct"):
        parent(inputs=(source, CandidateInput("fact", "Another")), facts=(fact,))
    # An input in a sibling entity cannot authorize this entity's fact.
    with pytest.raises(ValueError, match="original input"):
        parent(facts=(fact,))


def test_certification_has_only_formal_data_and_does_not_infer_status():
    cert = Certification("cert", "Credential", "Issuer", issued_at="2001", expires_at="2002")
    assert cert.status is None
    assert Certification("other", "Credential", "Issuer").expires_at is None
    assert {f.name for f in fields(cert)} == {"id", "name", "issuer", "issued_at", "expires_at", "status"}


@pytest.mark.parametrize("value", [
    CandidateInput("input", "Text"), ProfessionalFact("fact", "Statement", "input"),
    experience(), education(), Certification("cert", "Credential", "Issuer"), CandidatePast(),
])
def test_contracts_are_frozen(value):
    field = fields(value)[0].name
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, "Changed")


def test_mutable_collections_and_duplicate_entities_are_rejected():
    with pytest.raises(TypeError):
        CandidatePast(experiences=[experience()])
    with pytest.raises(TypeError):
        experience(inputs=[])
    with pytest.raises(TypeError):
        education(facts=[])
    with pytest.raises(ValueError):
        CandidatePast(experiences=(experience(), experience()))


@pytest.mark.parametrize("factory", [
    lambda: CandidateInput("", "Text"), lambda: CandidateInput("id", "  "),
    lambda: ProfessionalFact("id", "", "input"), lambda: experience(start_date=2020),
    lambda: education(status=""), lambda: Certification("id", "Name", ""),
])
def test_invalid_structural_values_fail_without_interpretation(factory):
    with pytest.raises(ValueError):
        factory()


def test_standalone_import_requires_no_application_infrastructure():
    root = Path(__file__).resolve().parents[1]
    script = """
import sys
class ForbidInfrastructure:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'services', 'streamlit', 'sqlite3', 'psycopg', 'openai', 'requests', 'httpx'}:
            raise AssertionError('Unexpected infrastructure: ' + fullname)
sys.meta_path.insert(0, ForbidInfrastructure())
from models.candidate_past import CandidatePast, Experience
assert CandidatePast(experiences=(Experience('e', 'Company', 'Role'),)).experiences[0].id == 'e'
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r})\n" + script],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
