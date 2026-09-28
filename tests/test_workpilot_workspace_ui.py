from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from models.product_state import CandidateProductState, WorkPilotMode


@pytest.mark.parametrize("mode", list(WorkPilotMode))
def test_dashboard_reads_active_candidate_without_mutating_domain(monkeypatch, mode):
    import components.dashboard as dashboard

    state = Mock()
    state.get.return_value = CandidateProductState(candidate_id="active", mode=mode)
    profiles = Mock()
    profiles.current_candidate.return_value = None
    applications = Mock()
    applications.list_applications.return_value = [
        {"application_group": "ready_to_apply"}, {"application_group": "interview"},
    ]
    jobs = Mock(return_value=[{"id": "job"}])
    market = Mock(return_value={"segments": ()})
    links = []
    monkeypatch.setattr(dashboard, "CandidateProductStateRepository", lambda: state)
    monkeypatch.setattr(dashboard, "ProfileSnapshotRepository", lambda: profiles)
    monkeypatch.setattr(dashboard, "ApplicationOutcomeRepository", lambda: applications)
    monkeypatch.setattr(dashboard, "list_candidate_jobs", jobs)
    monkeypatch.setattr(dashboard, "load_candidate_market_runtime", market)
    monkeypatch.setattr(st, "page_link", lambda page, **kwargs: links.append(page))
    app = AppTest.from_string('''
from types import SimpleNamespace
from components.dashboard import render_dashboard
render_dashboard(SimpleNamespace(candidate_id="active"))
''').run()
    assert not app.exception
    assert not app.metric
    state.get.assert_called_once_with("active")
    profiles.current_candidate.assert_called_once_with("active")
    applications.list_applications.assert_called_once_with("active")
    jobs.assert_called_once_with("active", "in_review")
    market.assert_called_once_with("active")
    assert len(state.mock_calls) == len(profiles.mock_calls) == len(applications.mock_calls) == 1
    assert "pages/1_Opportunities.py" not in links
    if mode == WorkPilotMode.READ_ONLY:
        assert any("history is preserved" in item.value for item in app.info)
        assert "pages/5_Applications.py" in links



def test_jobs_frontend_hides_internal_pool_and_uses_final_categories():
    source = Path("pages/1_Opportunities.py").read_text(encoding="utf-8")
    assert "Searching based on your profile" in source
    assert "We’re searching. Go grab a coffee" in source
    assert "Worth a Try" in source
    assert "You’re Strong, But" in source
    assert "How many opportunities would you like me to find?" not in source
    assert "opportunities currently available for screening" not in source
    assert "How this search worked" not in source
    assert "DEFAULT_OPPORTUNITY_TARGET = 10" in source
    assert "How many opportunities" not in source
    assert "and not scan_result.get(\"failed\", 0)" in source


def test_workspace_navigation_retains_hidden_oauth_route_and_dedicated_applications():
    import ast
    tree = ast.parse(Path("streamlit_app.py").read_text(encoding="utf-8"))
    pages = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "Page"]
    def config(path):
        return [{kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
                for node in pages if node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == path]
    assert config("pages/1_Opportunities.py")[0]["title"] == "Jobs"
    assert config("pages/2_Sources.py")[0]["visibility"] == "hidden"
    assert config("pages/2_Sources.py")[0]["url_path"] == "Sources"
    assert config("pages/5_Applications.py")
    assert config("pages/6_Settings.py")
    assert "applications_main()" in Path("pages/5_Applications.py").read_text()


def test_public_theme_has_no_seasonal_assets_or_authority_logic():
    source = Path("components/public_landing.py").read_text(encoding="utf-8")
    assert "autumn-web" not in source
    assert "public_seasonal.css" not in source
    assert "apply_theme()" in source
    assert "authenticate(" not in source


def test_profile_uses_official_strengths_not_absence_of_transferable_flag(monkeypatch):
    import services.profile_snapshot_repository as snapshots
    repository = Mock()
    repository.current_candidate.return_value = SimpleNamespace(
        profile_version=2, objectives=("Support operations",), evidence_gaps=("Licence not documented",),
        capabilities=(SimpleNamespace(label="Not proven by default", transferable=False),),
        checkpoint=SimpleNamespace(current_position="Support specialist", proven_strengths=("Incident triage",),
                                   transferable_strengths=("Stakeholder communication",)),
    )
    monkeypatch.setattr(snapshots, "ProfileSnapshotRepository", lambda: repository)
    app = AppTest.from_string('''
from components.workpilot_ui import render_profile_snapshot
render_profile_snapshot("active")
''').run()
    assert not app.exception
    text = "\n".join(item.value for item in app.markdown)
    assert "Incident triage" in text and "Stakeholder communication" in text
    assert "Not proven by default" not in text
    assert "Licence not documented" in text
    repository.current_candidate.assert_called_once_with("active")


def test_applications_workspace_uses_list_filters_and_same_page_details():
    import ast
    from pathlib import Path

    source = Path("app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    main = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "applications_main"
    )

    rendered = ast.unparse(main)

    for label in ("All", "Applied", "Interview", "Offer", "Closed"):
        assert label in rendered

    assert "st.tabs" not in rendered
    assert "st.radio" in rendered
    assert "st.expander" in rendered
    assert "_render_application_details" in rendered

    assert "Ready to apply" not in rendered
    assert "_application_filter_group" in rendered
    assert "_application_attention_message" in rendered




def test_application_details_are_stage_focused():
    import ast
    from pathlib import Path

    source = Path("app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_application_details"
    )

    rendered = ast.unparse(helper)

    # Applications must not embed the full Jobs analysis screen.
    assert "render_job_analysis" not in rendered
    assert "render_job(" not in rendered

    # Existing authoritative flows are still composed.
    assert "render_application_outcome" in rendered
    assert "render_interview_preparation" in rendered

    # Interview UI is stage-specific instead of always visible.
    group_values = {
        node.comparators[0].value
        for node in ast.walk(helper)
        if (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "group"
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Constant)
            and isinstance(node.comparators[0].value, str)
        )
    }

    assert {"applied", "interview", "offer", "closed"} <= group_values

    # Application utilities remain available.
    assert "save_notes" in rendered
    assert "external_application_url" in rendered



def test_applications_interview_uses_compact_round_ui():
    import ast
    from pathlib import Path

    source = Path("app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_application_details"
    )

    calls = [
        node
        for node in ast.walk(helper)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render_interview_preparation"
    ]

    assert calls

    assert any(
        any(
            keyword.arg == "compact"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in call.keywords
        )
        for call in calls
    )


def test_interview_round_ui_compact_mode_is_optional():
    import ast
    from pathlib import Path

    source = Path(
        "services/interview_preparation_ui.py"
    ).read_text(encoding="utf-8-sig")

    tree = ast.parse(source)

    render = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "render_interview_rounds"
    )

    args = {
        arg.arg: default
        for arg, default in zip(
            render.args.args[-len(render.args.defaults):],
            render.args.defaults,
        )
    }

    assert "compact" in [
        arg.arg
        for arg in (
            render.args.args
            + render.args.kwonlyargs
        )
    ]

    rendered = ast.unparse(render)

    assert "Add interview round" in rendered
    assert "Prepare for this interview" in rendered
    assert "Round feedback" in rendered
    assert "Questions to ask" in rendered





def test_applications_interview_shows_general_prep_before_rounds():
    import ast
    from pathlib import Path

    source = Path("app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    render = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "render_interview_preparation"
    )

    rendered = ast.unparse(render)

    assert "render_interview_preparation_overview" in rendered
    assert "render_interview_rounds" in rendered
    assert "Interview rounds" in rendered

    assert (
        rendered.index("render_interview_preparation_overview")
        < rendered.index("render_interview_rounds")
    )
