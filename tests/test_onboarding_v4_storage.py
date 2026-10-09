from dataclasses import replace
import sqlite3
from unittest.mock import Mock

import pytest

from models.candidate import Candidate
from models.candidate_onboarding import CandidateOnboarding
from models.company_interview import ConfirmedCompanyAnswer, V3_VERSION, V3_QUESTIONS
from models.onboarding_records import OnboardingEducationRecord, OnboardingCertificationRecord
from services import database
from services.candidate_repository import CandidateRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository


@pytest.fixture
def repo():
    for cid in ("a", "b"):
        CandidateRepository().save(Candidate(cid, "Synthetic", "", "", ""))
    return CandidateOnboardingRepository()


def test_about_you_round_trip_preserves_source_and_legacy(repo):
    source = CandidateOnboarding(
        "a", location="Legacy location", work_authorisation="Legacy declaration",
        spoken_languages=["English", "Portuguese"], desired_next_work="Legacy direction",
        enjoyed_work="Enjoyed", avoid_work="Avoid", development_interests="Develop",
        career_priorities=["Legacy label"], country=" Ireland ", city="Dublin",
        priority_declaration=" I prefer remote work and I wouldn't work weekends. ",
    )
    repo.save_onboarding(source)
    assert CandidateOnboardingRepository().get_onboarding("a") == source
    assert repo.get_onboarding("b") is None
    updated = replace(source, city="Cork", priority_declaration="New declaration")
    repo.save_onboarding(updated)
    assert repo.get_onboarding("a") == updated


def test_empty_v4_values_do_not_infer_from_legacy(repo):
    source = CandidateOnboarding("a", location="Dublin, Ireland", career_priorities=["Remote"])
    repo.save_onboarding(source)
    loaded = repo.get_onboarding("a")
    assert loaded == source
    assert (loaded.country, loaded.city, loaded.priority_declaration) == ("", "", "")
    assert loaded.spoken_languages == []


@pytest.mark.parametrize("changes", [
    {"candidate_id": " "}, {"country": None}, {"city": 1},
    {"priority_declaration": None}, {"spoken_languages": [1]},
    {"spoken_languages": [" "]},
])
def test_invalid_about_you_source_rejected(changes):
    with pytest.raises(ValueError):
        CandidateOnboarding(**({"candidate_id": "a"} | changes))


def test_mutated_invalid_onboarding_cannot_be_saved(repo):
    source = CandidateOnboarding("a")
    source.candidate_id = " "
    with pytest.raises(ValueError):
        repo.save_onboarding(source)


def test_role_round_trip_update_and_owner_isolation(repo):
    experience = repo.add_work_experience("a", "Synthetic", "2020-01", None, "Story", "Daily", role=" Analyst ")
    assert repo.list_work_experiences("a") == [experience]
    assert repo.list_work_experiences("b") == []
    with pytest.raises(ValueError):
        repo.update_work_experience(replace(experience, candidate_id="b", role="Other"))
    repo.update_work_experience(replace(experience, role="Senior analyst"))
    assert repo.list_work_experiences("a")[0].role == "Senior analyst"
    legacy = repo.add_work_experience("b", "Legacy", "2019-01", None, "", "")
    assert repo.list_work_experiences("b")[0].role == legacy.role == ""


def _answers():
    return [ConfirmedCompanyAnswer(f"q{i}", question, "text", f"Source {i}", False,
            V3_VERSION, V3_VERSION) for i, question in enumerate(V3_QUESTIONS, 1)]


def test_role_survives_draft_reload_and_confirmation(repo):
    kwargs = dict(candidate_id="a", experience_id="draft", company="Synthetic",
                  start_date="2020-01", end_date=None, role="Analyst")
    repo.begin_company_interview(**kwargs)
    repo.begin_company_interview(**kwargs)
    with pytest.raises(ValueError):
        repo.begin_company_interview(**(kwargs | {"role": "Changed"}))
    with pytest.raises(ValueError):
        repo.begin_company_interview(**(kwargs | {"candidate_id": "b"}))
    for answer in _answers():
        repo.save_company_answer(candidate_id="a", experience_id="draft", answer=answer)
    reopened = CandidateOnboardingRepository()
    assert reopened.get_company_draft("a", "draft")["role"] == "Analyst"
    assert reopened.get_company_draft("b", "draft") is None
    reopened.finalize_company_interview(candidate_id="a", experience_id="draft")
    item = reopened.list_work_experiences("a")[0]
    assert item.role == "Analyst"
    assert item.confirmed_interview_answers == _answers()


def test_direct_confirmation_persists_role(repo):
    repo.confirm_company_interview(candidate_id="a", experience_id="direct",
        company="Synthetic", start_date="2020-01", end_date=None, answers=_answers(), role="Analyst")
    assert repo.list_work_experiences("a")[0].role == "Analyst"


@pytest.mark.parametrize("kind", ["education", "certification"])
def test_source_records_multiple_stable_ids_and_scoped_delete(repo, kind):
    add = repo.add_education if kind == "education" else repo.add_certification
    listing = repo.list_education if kind == "education" else repo.list_certifications
    delete = repo.delete_education if kind == "education" else repo.delete_certification
    fields = (dict(institution=" Institution ", qualification="Degree", field="Computing")
              if kind == "education" else dict(name=" Certificate ", issuer="Issuer", year_obtained=2020))
    first = add(candidate_id="a", **fields)
    second = add(candidate_id="a", **fields)
    other = add(candidate_id="b", **fields)
    assert len({first.id, second.id, other.id}) == 3
    assert set(listing("a")) == {first, second}
    assert listing("b") == [other]
    reopened = CandidateOnboardingRepository()
    reload = reopened.list_education if kind == "education" else reopened.list_certifications
    assert set(reload("a")) == {first, second}
    with pytest.raises(ValueError, match="not found"):
        delete(first.id, "b")
    assert set(listing("a")) == {first, second}
    delete(first.id, "a")
    assert listing("a") == [second]
    assert listing("b") == [other]


@pytest.mark.parametrize("field", ["id", "candidate_id", "institution", "qualification", "field"])
@pytest.mark.parametrize("value", ["", " ", None, 1])
def test_education_rejects_invalid_fields(field, value):
    fields = dict(id="id", candidate_id="a", institution="School", qualification="Degree", field="Data")
    with pytest.raises(ValueError):
        OnboardingEducationRecord(**(fields | {field: value}))


@pytest.mark.parametrize("field", ["id", "candidate_id", "name", "issuer"])
@pytest.mark.parametrize("value", ["", " ", None, 1])
def test_certification_rejects_invalid_fields(field, value):
    fields = dict(id="id", candidate_id="a", name="Certificate", issuer="Issuer", year_obtained=2020)
    with pytest.raises(ValueError):
        OnboardingCertificationRecord(**(fields | {field: value}))


@pytest.mark.parametrize("year", [None, "2020", 2020.0, True, False, 0, -1, 10000])
def test_certification_rejects_invalid_year(repo, year):
    with pytest.raises(ValueError):
        repo.add_certification(candidate_id="a", name="Certificate", issuer="Issuer", year_obtained=year)
    assert repo.list_certifications("a") == []


def test_invalid_education_not_persisted(repo):
    with pytest.raises(ValueError):
        repo.add_education(candidate_id="a", institution=" ", qualification="Degree", field="Data")
    assert repo.list_education("a") == []


def test_legacy_migration_is_additive_idempotent_and_preserves_new_data():
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE TABLE candidates (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO candidates VALUES ('a')")
        connection.execute("""CREATE TABLE candidate_onboarding
            (candidate_id TEXT PRIMARY KEY, location TEXT, spoken_languages_json TEXT, career_priorities_json TEXT)""")
        connection.execute("""INSERT INTO candidate_onboarding VALUES ('a', 'Legacy', '["English"]', '["Remote"]')""")
        connection.execute("""CREATE TABLE candidate_work_experiences
            (id TEXT PRIMARY KEY, candidate_id TEXT, company TEXT, day_to_day_narrative TEXT)""")
        connection.execute("INSERT INTO candidate_work_experiences VALUES ('old', 'a', 'Legacy', 'Original')")
        database.create_onboarding_v4_schema(connection)
        database.create_onboarding_v4_schema(connection)
        row = dict(connection.execute("SELECT * FROM candidate_onboarding").fetchone())
        assert row == dict(candidate_id="a", location="Legacy", spoken_languages_json='["English"]',
            career_priorities_json='["Remote"]', country="", city="", priority_declaration="")
        experience = dict(connection.execute("SELECT * FROM candidate_work_experiences").fetchone())
        assert experience == dict(id="old", candidate_id="a", company="Legacy", day_to_day_narrative="Original", role="")
        connection.execute("UPDATE candidate_onboarding SET country = 'Ireland', priority_declaration = 'Source'")
        connection.execute("UPDATE candidate_work_experiences SET role = 'Analyst'")
        connection.execute("INSERT INTO candidate_onboarding_education VALUES ('e', 'a', 'School', 'Degree', 'Data')")
        connection.execute("INSERT INTO candidate_onboarding_certifications VALUES ('c', 'a', 'Cert', 'Issuer', 2020)")
        database.create_onboarding_v4_schema(connection)
        assert connection.execute("SELECT role FROM candidate_work_experiences").fetchone()[0] == "Analyst"
        assert tuple(connection.execute("SELECT country, priority_declaration FROM candidate_onboarding").fetchone()) == ("Ireland", "Source")
        assert connection.execute("SELECT COUNT(*) FROM candidate_onboarding_education").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM candidate_onboarding_certifications").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO candidate_onboarding_education VALUES ('bad', 'missing', 'S', 'Q', 'F')")


def test_postgres_migration_statements_are_additive_and_server_only(monkeypatch):
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    connection = Mock()
    database.create_onboarding_v4_schema(connection)
    statements = [call.args[0] for call in connection.execute.call_args_list]
    for table, field in (("candidate_onboarding", "country"), ("candidate_onboarding", "city"),
                         ("candidate_onboarding", "priority_declaration"), ("candidate_work_experiences", "role")):
        assert f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {field} TEXT NOT NULL DEFAULT ''" in statements
    for table in ("candidate_onboarding_education", "candidate_onboarding_certifications"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"REVOKE ALL ON TABLE {table} FROM PUBLIC" in statements
        assert any(f"REVOKE ALL ON TABLE {table} FROM authenticated" in sql for sql in statements)
        assert any(f"REVOKE ALL ON TABLE {table} FROM anon" in sql for sql in statements)
    assert not any(sql.lstrip().upper().startswith(("DROP ", "DELETE ", "UPDATE ", "INSERT ")) for sql in statements)
