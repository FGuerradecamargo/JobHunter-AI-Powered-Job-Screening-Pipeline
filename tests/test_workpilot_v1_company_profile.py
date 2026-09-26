from dataclasses import asdict, fields, replace

import pytest

from models.company_profile import CompanyClaim, CompanyProfileDraft, CompanyProfileSnapshot, CompanyPublicSource
from services.company_profile_builder import build_company_profile
from services.company_profile_repository import CompanyProfileRepository
from services.company_repository import CompanyRepository


def source(company_id="company-1", **changes):
    return CompanyPublicSource(**{**dict(ref="web:company", company_id=company_id,
        source_type="company_website", summary="Provides software. We value collaboration."), **changes})


def build(company_id="company-1", **changes):
    return build_company_profile(**{**dict(company_id=company_id, sources=(source(company_id),),
        draft=CompanyProfileDraft(), created_at="2026-09-26T00:00:00+00:00"), **changes})


@pytest.mark.parametrize("ref", ["gmail:x", "GMAIL:x", "private:x", "user:x", "manual:x"])
def test_private_source_rejected_even_when_declared_public(ref):
    with pytest.raises(ValueError):
        source(ref=ref)


def test_public_flag_type_and_source_type_fail_closed():
    for changes in ({"public": False}, {"public": "true"}, {"source_type": "gmail"}):
        with pytest.raises(ValueError):
            source(**changes)


def test_unknown_and_no_candidate_or_personal_life_fields():
    p = build()
    assert p.what_they_do == p.size_context == ""
    assert p.products_services == p.public_culture_signals == ()
    assert not hasattr(p, "candidate_id")
    assert not {"interviewer", "family", "politics", "health", "hobbies"} & {f.name for f in fields(p)}


def test_claims_require_support_and_remain_attributed():
    draft = CompanyProfileDraft(what_they_do="Provides software.",
        public_culture_signals=("We value collaboration.",), claims=(
            CompanyClaim("what_they_do", "Provides software.", "web:company"),
            CompanyClaim("public_culture_signals", "We value collaboration.", "web:company")))
    p = build(draft=draft)
    assert all(c.attribution == "source_reported" for c in p.claims)
    assert p.sources[0].summary == source().summary
    with pytest.raises(ValueError):
        build(draft=replace(draft, size_context="10000 employees"))
    with pytest.raises(ValueError):
        build(draft=CompanyProfileDraft(what_they_do="Invented", claims=(CompanyClaim("what_they_do", "Invented", "web:company"),)))
    with pytest.raises(ValueError):
        CompanyClaim("public_culture_signals", "We value collaboration.", "web:company", "verified")


def test_history_scope_and_source_scope_checked():
    with pytest.raises(ValueError, match="scope"):
        build("other", sources=(source(),))
    with pytest.raises(ValueError, match="scope"):
        build("other", previous=build())


def test_same_evidence_reuses_changed_source_versions_and_order_independent():
    first = build()
    assert build(previous=first) is first
    second = build(previous=first, sources=(source(summary="New information"),))
    assert second.profile_version == 2 and second.supersedes_version == 1
    assert second.source_signature != first.source_signature
    sources = (source(), source(ref="web:filing", source_type="public_filing"))
    assert build(sources=sources) == build(sources=tuple(reversed(sources)))


def test_registry_history_roundtrip_idempotency_and_race():
    company = CompanyRepository().get_or_create_company("Example", domain="example.com")
    repo = CompanyProfileRepository()
    first = build(company.id)
    repo.save(first)
    repo.save(first)
    second = build(company.id, sources=(source(company.id, summary="New information"),), previous=first)
    repo.save(second)
    assert repo.current(company.id) == second
    assert repo.version(company.id, 1) == first
    assert repo.for_signature(company.id, first.source_signature) == first
    assert repo.current("other") is None
    with pytest.raises(ValueError, match="reload"):
        repo.save(build(company.id, sources=(source(company.id, summary="Racing writer"),), previous=first))
    assert repo.current(company.id) == second


def test_company_builder_cannot_mutate_candidate_or_job_contracts():
    from models.profile_interpretation import CandidateProfileSnapshot, ProfileCheckpoint, AIJobProfileSnapshot
    c = CandidateProfileSnapshot(candidate_id="c", profile_version=1, memory_signature="m",
        created_at="2026-09-26T00:00:00+00:00", source_refs=(), capabilities=(), checkpoint=ProfileCheckpoint(current_position=""))
    # No candidate/job input or field exists on the company builder boundary.
    import inspect
    assert not {"candidate_profile", "job_profile"} & set(inspect.signature(build_company_profile).parameters)
    before = asdict(c)
    j = AIJobProfileSnapshot(job_id="j", profile_version=1, job_signature="s", created_at=c.created_at, needs=())
    job_before = asdict(j)
    build()
    assert asdict(c) == before
    assert asdict(j) == job_before
    assert "company_profile" not in {f.name for f in fields(AIJobProfileSnapshot)}


def test_postgres_schema_is_additive_and_protected(monkeypatch):
    from services import database
    class Recorder:
        def __init__(self):
            self.sql = []
        def execute(self, sql, *args):
            self.sql.append(sql)
    connection = Recorder()
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    database.create_company_registry_schema(connection)
    sql = "\n".join(connection.sql)
    assert "company_profile_snapshots ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE company_profile_snapshots FROM PUBLIC" in sql
    assert "REFERENCES companies(id)" in sql
    assert "DROP TABLE" not in sql
