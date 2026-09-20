import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.opportunity_search_run import OpportunitySearchRun


ROOT = Path(__file__).resolve().parents[1]
SCOPE = ("actor", "owner", "candidate", "signature")


def make_run():
    return OpportunitySearchRun(*SCOPE, target=10, aggregate={"kept": []})


def test_stop_before_first_unit():
    run = make_run()
    assert run.stop(SCOPE, run.scan_id)
    unit = Mock()
    run.advance(SCOPE, unit)
    unit.assert_not_called()
    assert run.status == "stopped"


def test_stop_after_three_preserves_results_and_starts_no_more_work():
    run = make_run()
    def unit():
        run.aggregate["kept"].append(len(run.aggregate["kept"]))
        return True
    for _ in range(3):
        run.advance(SCOPE, unit)
    run.stop(SCOPE, run.scan_id)
    for _ in range(5):
        run.advance(SCOPE, unit)
    assert run.aggregate["kept"] == [0, 1, 2]
    assert run.status == "stopped"


@pytest.mark.parametrize("index", range(4))
def test_cross_actor_active_user_candidate_or_context_cannot_cancel_or_advance(index):
    run = make_run()
    other = list(SCOPE)
    other[index] = "other"
    assert not run.stop(tuple(other), run.scan_id)
    unit = Mock()
    run.advance(tuple(other), unit)
    unit.assert_not_called()
    assert run.status == "running"


def test_fresh_run_and_other_tab_unaffected_by_old_stop():
    old, new, other_tab = make_run(), make_run(), make_run()
    old.stop(SCOPE, old.scan_id)
    assert not new.stop(SCOPE, old.scan_id)
    for run in (new, other_tab):
        unit = Mock(return_value=False)
        run.advance(SCOPE, unit)
        unit.assert_called_once()
        assert run.status == "complete"


@pytest.mark.parametrize("cancel", [False, True])
def test_failure_keeps_partial_results_and_never_retries(cancel):
    run = make_run()
    def unit():
        run.aggregate["kept"].append("saved")
        if cancel:
            run.stop(SCOPE, run.scan_id)
        raise RuntimeError("private error")
    run.advance(SCOPE, unit)
    assert run.status == ("stopped" if cancel else "failed")
    assert run.aggregate["kept"] == ["saved"]
    run.advance(SCOPE, Mock(side_effect=AssertionError("must not retry")))


def test_in_flight_unit_finishes_without_overwriting_stop():
    run = make_run()
    def unit():
        run.stop(SCOPE, run.scan_id)
        run.aggregate["kept"].append("saved")
        return False
    run.advance(SCOPE, unit)
    assert run.status == "stopped"
    assert run.aggregate["kept"] == ["saved"]


@pytest.fixture
def page_unit():
    tree = ast.parse((ROOT / "pages/1_Opportunities.py").read_text(encoding="utf-8"))
    names = {"empty_scan_result", "merge_scan_result", "merge_activation_result",
             "advance_opportunity_search", "stop_opportunity_scan"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = dict(repository=Mock(), analysis_service=Mock(), candidate_id="candidate", BATCH_MAX_SIZE=10,
               candidate_signature="signature", ANALYSIS_VERSION="version",
               candidate=SimpleNamespace(target_role_families=[], bridge_role_families=[],
                                         competitive_role_families=[]),
               ensure_candidate_job_analysis=Mock(return_value=True),
               activate_ready_opportunities=Mock(return_value={"job_ids": []}))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "opportunities", "exec"), env)
    run = OpportunitySearchRun(*SCOPE, target=10, aggregate=env["empty_scan_result"]())
    env["search_run"] = run
    env["st"] = SimpleNamespace(session_state={"opportunity_search_run": run})
    env["repository"].list_jobs_to_analyze_for_candidate.return_value = [{"id": "job"}]
    env["analysis_service"].analyze_pending.return_value = {"analyzed": 1, "selected": 1}
    return env


def test_real_page_unit_initial_activation_then_one_job_per_rerun(page_unit):
    env = page_unit
    run = env["search_run"]
    run.advance(SCOPE, env["advance_opportunity_search"])
    env["analysis_service"].analyze_pending.assert_not_called()
    run.advance(SCOPE, env["advance_opportunity_search"])
    env["analysis_service"].analyze_pending.assert_called_once_with(
        candidate_id="candidate", limit=1, ai_budget=None, job_ids=["job"], scan_id=run.scan_id,
        prepare_only=True)
    assert env["repository"].list_jobs_to_analyze_for_candidate.call_args.kwargs["limit"] == 1
    assert run.aggregate["selected"] == 1
    env["stop_opportunity_scan"](SCOPE, run.scan_id)
    run.advance(SCOPE, env["advance_opportunity_search"])
    assert env["analysis_service"].analyze_pending.call_count == 1


@pytest.mark.parametrize("result", [{"analyzed": 1, "usage_limit_reached": True},
                                     {"analyzed": 1, "provider_quota_exhausted": True}])
def test_page_no_progress_or_quota_finishes_without_retry(page_unit, result):
    run = page_unit["search_run"]
    run.initialized = True
    page_unit["analysis_service"].analyze_pending.return_value = result
    run.advance(SCOPE, page_unit["advance_opportunity_search"])
    assert run.status == "complete"


def test_page_partial_activation_and_target_preserved(page_unit):
    run = page_unit["search_run"]
    run.initialized = True
    run.target = 1
    page_unit["activate_ready_opportunities"].return_value = {"job_ids": ["job"], "best_match": 1}
    run.advance(SCOPE, page_unit["advance_opportunity_search"])
    assert run.aggregate["opportunities_found"] == 1
    assert run.aggregate["activated_best_match"] == 1
    assert run.status == "complete"


def test_claim_lost_after_selection_skips_job_and_continues(page_unit):
    env = page_unit
    run = env["search_run"]
    run.initialized = True
    remaining = [{"id": "busy"}, {"id": "available"}]
    def select(**kwargs):
        return [row for row in remaining if row["id"] not in kwargs.get("exclude_job_ids", [])][:1]
    env["repository"].list_jobs_to_analyze_for_candidate.side_effect = select
    env["analysis_service"].analyze_pending.side_effect = [
        {"selected": 0, "analyzed": 0}, {"selected": 1, "analyzed": 1},
    ]
    run.advance(SCOPE, env["advance_opportunity_search"])
    assert run.status == "running"
    run.advance(SCOPE, env["advance_opportunity_search"])
    assert run.status == "running"
    assert run.aggregate["selected"] == 1
    assert [call.kwargs["job_ids"] for call in env["analysis_service"].analyze_pending.call_args_list] == [["busy"], ["available"]]
    remaining.clear()
    run.advance(SCOPE, env["advance_opportunity_search"])
    assert run.status == "complete"
    assert env["analysis_service"].analyze_pending.call_count == 2


def test_unavailable_only_pool_finishes_without_retry_and_fresh_run_is_clean(page_unit):
    env = page_unit
    run = env["search_run"]
    run.initialized = True
    env["repository"].list_jobs_to_analyze_for_candidate.side_effect = (
        lambda **kw: [] if "busy" in kw["exclude_job_ids"] else [{"id": "busy"}]
    )
    env["analysis_service"].analyze_pending.return_value = {"selected": 0, "analyzed": 0}
    run.advance(SCOPE, env["advance_opportunity_search"])
    assert run.status == "running"
    run.advance(SCOPE, env["advance_opportunity_search"])
    assert run.status == "complete"
    assert env["analysis_service"].analyze_pending.call_count == 1
    fresh = OpportunitySearchRun(*SCOPE, target=5, aggregate=env["empty_scan_result"]())
    assert fresh.unavailable_job_ids == set()
    assert run.unavailable_job_ids == {"busy"}


@pytest.mark.parametrize("flag", ["usage_limit_reached", "provider_quota_exhausted", "failed"])
def test_empty_selection_with_stop_or_failure_is_not_retried(page_unit, flag):
    run = page_unit["search_run"]
    run.initialized = True
    page_unit["analysis_service"].analyze_pending.return_value = {
        "selected": 0, "analyzed": 0, flag: 1,
    }
    run.advance(SCOPE, page_unit["advance_opportunity_search"])
    assert run.status == ("failed" if flag == "failed" else "complete")
    assert not run.unavailable_job_ids
    run.advance(SCOPE, page_unit["advance_opportunity_search"])
    assert page_unit["analysis_service"].analyze_pending.call_count == 1


def test_ui_has_no_blocking_loop_and_renders_results_before_advancing():
    tree = ast.parse((ROOT / "pages/1_Opportunities.py").read_text(encoding="utf-8"))
    search_nodes = [n for n in tree.body if not isinstance(n, ast.FunctionDef)
                    or n.name == "advance_opportunity_search"]
    assert not any(isinstance(n, ast.While) for root in search_nodes for n in ast.walk(root))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    advances = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "advance"]
    stops = [n for n in calls if n.args and isinstance(n.args[0], ast.Constant)
             and n.args[0].value == "Stop search"]
    renders = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "render_job"]
    assert len(advances) == len(stops) == 1
    assert stops[0].lineno < advances[0].lineno
    assert max(n.lineno for n in renders) < advances[0].lineno
    assert isinstance(tree.body[-1], ast.If)
    assert tree.body[-1].body[-1].value.func.attr == "rerun"


def test_streamlit_queued_stop_survives_automatic_rerun(page_unit):
    # Exercise the installed Streamlit queue, not an assumed rerun model.
    from streamlit.proto.WidgetStates_pb2 import WidgetStates
    from streamlit.runtime.scriptrunner_utils.script_requests import RerunData, ScriptRequests

    queue = ScriptRequests()
    click = WidgetStates()
    click.widgets.add(id="stop_opportunity_search", trigger_value=True)
    queue.request_rerun(RerunData(widget_states=click))
    queue.request_rerun(RerunData())
    request = queue.on_scriptrunner_yield()
    assert request.rerun_data.widget_states.widgets[0].trigger_value
    run = page_unit["search_run"]
    page_unit["stop_opportunity_scan"](SCOPE, run.scan_id)
    run.advance(SCOPE, page_unit["advance_opportunity_search"])
    page_unit["analysis_service"].analyze_pending.assert_not_called()


def test_returned_analysis_failure_preserves_results_and_stops(page_unit):
    run = page_unit["search_run"]
    run.initialized = True
    run.aggregate["opportunities_found"] = 3
    page_unit["analysis_service"].analyze_pending.return_value = {"analyzed": 0, "failed": 1}
    run.advance(SCOPE, page_unit["advance_opportunity_search"])
    assert run.status == "failed"
    assert run.aggregate["opportunities_found"] == 3


def test_logout_or_expiry_discards_run_and_search_cache():
    tree = ast.parse((ROOT / "services/session_auth.py").read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_clear_local_session")
    state = {"opportunity_search_run": make_run(), "scan_requested": True,
             "scan_in_progress": True, "last_scan_result": {"opportunities_found": 3}}
    class Cookies(dict):
        def save(self):
            pass
    env = dict(st=SimpleNamespace(session_state=state), cookies=Cookies(), SESSION_COOKIE="session")
    exec(compile(ast.Module(body=[function], type_ignores=[]), "session_auth", "exec"), env)
    env["_clear_local_session"]()
    assert set(state) == {"reauthentication_required"}


def test_streamlit_runtime_mode_does_not_disable_opportunity_search():
    import tomllib

    config = tomllib.loads(
        (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    )
    assert config["runner"]["fastReruns"] is False

    source = (
        ROOT / "pages/1_Opportunities.py"
    ).read_text(encoding="utf-8")

    assert 'st.get_option("runner.fastReruns")' not in source
    assert "search_execution_ready = True" in source
    assert "Search is temporarily unavailable." not in source


def test_streamlit_stop_button_preserves_partial_and_new_search_works():
    from streamlit.testing.v1 import AppTest

    source = (ROOT / "pages/1_Opportunities.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    empty = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "empty_scan_result")
    # Actual production controls with fake dependencies; omit the footer's
    # automatic advance so the test can click between deterministic units.
    controls = source[source.index("search_scope = ("):source.index("\nscan_result = st.session_state.get(")]
    script = '''
import streamlit as st
from types import SimpleNamespace
from unittest.mock import Mock
from services.opportunity_search_run import OpportunitySearchRun
authenticated_user = SimpleNamespace(id="actor")
active_user = SimpleNamespace(id="owner")
candidate_id = "candidate"
candidate_signature = "signature"
ANALYSIS_VERSION = "version"
BATCH_MAX_SIZE = 10
OPPORTUNITY_TARGETS = {"Quick": 5, "Standard": 10}
repository = Mock()
repository.count_jobs_to_analyze_for_candidate.return_value = 10
analysis_service = Mock()
analysis_configuration_error = ""
AIUsageBudget = SimpleNamespace(unlimited=lambda: None)
''' + ast.get_source_segment(source, empty) + '''
if "seeded" not in st.session_state:
    run = OpportunitySearchRun("actor", "owner", "candidate", "signature", 10, empty_scan_result())
    run.aggregate["opportunities_found"] = 3
    st.session_state["opportunity_search_run"] = run
    st.session_state["seeded"] = True
''' + controls
    app = AppTest.from_string(script).run()
    assert not app.exception
    original_id = app.session_state["opportunity_search_run"].scan_id
    next(b for b in app.button if b.label == "Stop search").click().run()
    assert not app.exception
    assert app.session_state["opportunity_search_run"].status == "stopped"
    assert any(i.value == "Search stopped. 3 opportunities kept." for i in app.info)
    assert app.session_state["last_scan_result"]["opportunities_found"] == 3
    next(b for b in app.button if b.label == "Find opportunities for me").click().run()
    assert not app.exception
    assert app.session_state["opportunity_search_run"].status == "running"
    assert app.session_state["opportunity_search_run"].scan_id != original_id
