"""Render the actual search feedback and result-list blocks with offline data."""
import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def render_feedback(status, *, quota=False, saved=True, found=0):
    source = (ROOT / "pages/1_Opportunities.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    empty = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "empty_scan_result")
    feedback = source[source.index("\nif search_run is not None:\n"):
                      source.index("# Market Position\n")]
    result_list = source[source.index("\nif (\n    best_matches\n"):
                         source.index("# Render partial opportunities")]
    script = '''
import streamlit as st
from types import SimpleNamespace
from services.opportunity_search_run import OpportunitySearchRun
BATCH_MAX_SIZE = 10
candidate_id = "candidate"
candidate_signature = "signature"
ANALYSIS_VERSION = "version"
repository = SimpleNamespace(count_jobs_to_analyze_for_candidate=lambda **kw: 1322)
pool_available = repository.count_jobs_to_analyze_for_candidate()
stop_opportunity_scan = lambda *args: None
''' + ast.get_source_segment(source, empty) + f'''
aggregate = empty_scan_result()
aggregate.update(selected=22, hard_rejected=2, ai_eligible=20,
                 ai_analyses_created=10, opportunities_found={found},
                 activated_best_match={found}, failed={10 if quota else 0},
                 provider_quota_exhausted={quota!r})
aggregate["errors"] = [{{"error": "PRIVATE_PROVIDER_DETAIL"}} for _ in range({10 if quota else 0})]
search_run = OpportunitySearchRun("actor", "owner", "candidate", "signature", 5, aggregate,
                                  status={status!r}, prepared_job_ids=["j1", "j2", "j3"])
search_scope = search_run.scope
st.session_state["opportunity_search_run"] = search_run
best_matches = [{{"id": "saved-job"}}] if {saved!r} else []
potential_jobs = []
good_opportunities = []
render_job = lambda job: st.write("Saved opportunity: " + job["id"])
render_opportunity_category_header = lambda *args: None
render_empty_category = lambda text: st.caption(text)
''' + feedback + result_list
    app = AppTest.from_string(script).run()
    assert not app.exception
    return app


def visible_text(app):
    return "\n".join(str(element.value) for kind in
                     ("info", "success", "warning", "markdown", "caption")
                     for element in getattr(app, kind))


def test_running_search_shows_actual_progress_not_final_summary():
    app = render_feedback("running")
    text = visible_text(app)
    assert "Searching for opportunities..." in text
    assert "Reviewed: 22" in text
    assert "Passed initial screening: 20" in text
    assert "Preparing deeper analysis: 3/10" in text
    assert "WorkPilot is still searching." in text
    assert "I found" not in text
    assert "How this search worked" not in [e.label for e in app.expander]
    assert "1,322 more opportunities available." in text
    assert "Saved opportunity: saved-job" in text


@pytest.mark.parametrize("status", ["failed", "complete"])
def test_atomic_quota_failure_has_one_batch_message_and_preserves_results(status):
    app = render_feedback(status, quota=True, found=2)
    assert len(app.warning) == 1
    assert app.warning[0].value == (
        "We couldn't continue the deeper analysis right now. "
        "Your existing results are safe, and these opportunities can be analyzed again later."
    )
    text = visible_text(app)
    assert "job(s) failed" not in text
    assert "An opportunity could not be analyzed" not in text
    assert "Search could not finish" not in text
    assert "PRIVATE_PROVIDER_DETAIL" not in text
    assert "OpenAI" not in text
    assert "Saved opportunity: saved-job" in text
    result = app.session_state["last_scan_result"]
    assert result["opportunities_found"] == 2
    assert result["failed"] == 10
    assert len(result["errors"]) == 10  # Presentation never erases diagnostic history.


def test_completed_search_still_shows_normal_summary():
    app = render_feedback("complete", found=5)
    assert app.success[0].value == "I found 5 relevant opportunities for you after reviewing 22 jobs."
    assert "WorkPilot is still searching." not in visible_text(app)
    assert "How this search worked" in [e.label for e in app.expander]
    assert "Saved opportunity: saved-job" in visible_text(app)
    assert not app.warning


@pytest.mark.parametrize("status,quota", [("running", False), ("failed", True)])
def test_incomplete_search_does_not_claim_no_jobs_met_threshold(status, quota):
    app = render_feedback(status, quota=quota, saved=False)
    assert "This scan did not identify" not in str(app.get("html"))
