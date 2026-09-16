import ast
from collections import Counter
from contextlib import nullcontext
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.candidate import Candidate
from models.candidate_profile import CandidateProfile
from models.job import Job
from models.job_profile import JobProfile
from services import database
from services.candidate_repository import CandidateRepository
from services.historical_cv_presenter import normalize_historical_cv
from services.analyzers.hard_filter_analyzer import HardFilterAnalyzer
from services.ai.response_parser import parse_response


def test_test_database_cannot_use_ambient_postgres(monkeypatch, tmp_path):
    assert database.DATABASE_FILE.is_relative_to(tmp_path)
    assert not os.environ.get("DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid.example/production")
    with pytest.raises(RuntimeError, match="External databases are forbidden"):
        with database.get_connection():
            pytest.fail("Must not connect")


def test_fixture_job_and_analysis_never_reach_separate_application_db(tmp_path, monkeypatch):
    fixture_path = database.DATABASE_FILE
    database.upsert_raw_job(Job(id="fixture", title="Fraud Operations Analyst", company="Postgres Test Co",
                               raw_text="Synthetic", url="https://example.test/fixture"))
    CandidateRepository().save(Candidate("synthetic", "Synthetic", "Operations", "mid", "Fixture"))
    database.ensure_candidate_job_analysis("synthetic", "fixture")
    database.save_candidate_job_analysis(candidate_id="synthetic", job_id="fixture",
        analysis={"recommendation":"best_match","bucket":"best_match"},
        job_signature="fixture", candidate_signature="fixture", analysis_version="test",
        opportunity_state="active")
    assert len(database.list_candidate_jobs("synthetic", "in_review")) == 1
    app_path = tmp_path / "application.db"
    monkeypatch.setattr(database, "DATABASE_FILE", app_path)
    database.initialize_database.cache_clear()
    database.initialize_database()
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM candidate_job_analyses").fetchone()[0] == 0
    assert fixture_path != app_path


def test_opportunity_query_keeps_candidate_analysis_separate():
    for candidate_id in ("owner", "other"):
        CandidateRepository().save(Candidate(candidate_id, "Synthetic", "Operations", "mid", "Fixture"))
    database.upsert_raw_job(Job(id="shared", raw_text="Public vacancy", url="https://example.test/real", title="Operations"))
    for candidate_id, bucket in (("owner", "potential"), ("other", "best_match")):
        database.ensure_candidate_job_analysis(candidate_id, "shared")
        database.save_candidate_job_analysis(candidate_id=candidate_id, job_id="shared",
            analysis={"recommendation":bucket,"bucket":bucket,"current_fit":60,"growth_value":50},
            job_signature="job", candidate_signature=candidate_id, analysis_version="test",
            opportunity_state="active")
    owner = database.list_candidate_jobs("owner", "in_review")
    other = database.list_candidate_jobs("other", "in_review")
    assert [j["analysis"]["bucket"] for j in owner] == ["potential"]
    assert [j["analysis"]["bucket"] for j in other] == ["best_match"]
    assert database.list_candidate_jobs("stranger", "in_review") == []


@pytest.mark.parametrize("value", [None, {}, [], "-\n*", {"key_skills":["-","*",None,{}]}, '{broken'])
def test_empty_or_malformed_legacy_cv_is_omitted(value):
    assert normalize_historical_cv(value) is None


def test_legacy_cv_string_lists_are_not_iterated_by_character():
    cv = normalize_historical_cv(json.dumps({"key_skills":"- SQL\n* Reporting\n-\n*",
        "experiences":json.dumps([{"role":"Analyst","tailored_bullets":"- Reviewed cases\n* Improved reporting"}]),
        "additional_relevant_information":'["English", "-", null]'}))
    assert cv["key_skills"] == ["SQL", "Reporting"]
    assert cv["experiences"][0]["tailored_bullets"] == ["Reviewed cases", "Improved reporting"]
    assert cv["additional_relevant_information"] == ["English"]


def test_nested_serialized_skills_and_markdown_emphasis_are_readable():
    cv = normalize_historical_cv({"key_skills":['["SQL", "**Reporting**"]', '{broken', {}]})
    assert cv["key_skills"] == ["SQL", "Reporting"]


def test_actual_page_renderer_uses_normalized_content_for_screen_and_exports():
    path = Path(__file__).parents[1] / "pages" / "1_Opportunities.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in
                 {"render_tailored_cv", "clean_display_bullet", "build_cv_filename"}]
    shown, exported = [], []
    st = SimpleNamespace(expander=lambda *a: nullcontext(), text=shown.append,
                         subheader=lambda *a: None, columns=lambda n:[nullcontext() for _ in range(n)],
                         download_button=lambda *a,**kw: None)
    def export(**kwargs):
        exported.append(kwargs["tailored_cv"])
        return b"fixture"
    namespace = dict(st=st, normalize_historical_cv=normalize_historical_cv,
                     render_tailored_cv_docx=export, render_tailored_cv_pdf=export)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    namespace["render_tailored_cv"]({"tailored_cv":{"key_skills":"- SQL\n*\n-"}}, "Synthetic", "Company", "Role")
    assert shown == ["- SQL"]
    assert len(exported) == 2
    assert all(cv["key_skills"] == ["SQL"] for cv in exported)


@pytest.mark.parametrize("target,title,expected", [
    ("Business Analyst", "Business Analyst - Trade Finance", True),
    ("Fraud Operations Analyst", "Fraud Operations Analyst", True),
    ("Risk Operations", "Risk Operations Analyst", True),
    ("Business Analyst", "Mechanical Engineering Analyst", False),
    ("Business Analyst", "Investment Analyst", False),
    ("analyst", "PMO Analyst", False),
    ("analyst", "Contract Analyst II", False),
])
def test_direction_diagnostics_preserve_specific_and_conservative_matching(target, title, expected):
    analyzer = HardFilterAnalyzer(CandidateProfile(target_roles=[target]))
    assert analyzer._role_matches_direction(JobProfile(job_id="fixture", canonical_role=title)) is expected


@pytest.mark.parametrize("fit,growth", [(30,95),(65,40),(85,80)])
def test_potential_is_model_label_not_a_numeric_threshold(fit, growth):
    data = dict(recommendation="potential",competitive_status="bridge_opportunity",
                direction_alignment="high",current_fit=fit,growth_value=growth)
    result = parse_response(json.dumps(data), "fixture")
    assert result.recommendation == "potential"
    assert (result.current_fit,result.growth_value) == (fit,growth)


def test_reported_distribution_arithmetic_is_not_live_remeasurement():
    sample = Counter(best_match=1, potential=15, good_opportunity=3)
    sample.subtract({"best_match":1})
    assert sample == Counter(best_match=0,potential=15,good_opportunity=3)
