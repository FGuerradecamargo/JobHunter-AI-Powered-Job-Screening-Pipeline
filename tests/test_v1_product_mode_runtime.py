from pathlib import Path

from models.product_state import CandidateProductState, WorkPilotMode
from services.product_mode_policy import product_mode_policy


def state(mode):
    return CandidateProductState(
        candidate_id="candidate-1",
        mode=mode,
    )


def test_search_mode_allows_search_and_normal_writes():
    policy = product_mode_policy(
        state(WorkPilotMode.SEARCH)
    )

    assert policy.can_search
    assert policy.can_mutate
    assert policy.show_sources
    assert policy.show_profile
    assert policy.show_improvements
    assert not policy.can_return_to_search


def test_career_mode_pauses_search_but_keeps_career_workspace():
    policy = product_mode_policy(
        state(WorkPilotMode.CAREER)
    )

    assert not policy.can_search
    assert policy.can_mutate
    assert policy.show_sources
    assert policy.show_profile
    assert policy.show_improvements
    assert policy.can_return_to_search


def test_read_only_preserves_views_without_write_surfaces():
    policy = product_mode_policy(
        state(WorkPilotMode.READ_ONLY)
    )

    assert not policy.can_search
    assert not policy.can_mutate
    assert not policy.show_sources
    assert not policy.show_profile
    assert policy.show_improvements
    assert not policy.can_return_to_search


def test_global_shell_uses_product_mode_navigation():
    source = Path("streamlit_app.py").read_text(
        encoding="utf-8"
    )

    assert "product_mode_policy(product_state)" in source
    assert "if product_policy.can_search:" in source
    assert "if product_policy.show_sources:" in source
    assert "if product_policy.show_profile:" in source
    assert "if product_policy.show_improvements:" in source
    assert ".return_to_search(" in source
    assert '"READ-ONLY MODE"' in source


def test_direct_routes_fail_closed_for_disallowed_modes():
    opportunities = Path(
        "pages/1_Opportunities.py"
    ).read_text(encoding="utf-8")

    sources = Path(
        "pages/2_Sources.py"
    ).read_text(encoding="utf-8")

    profile = Path(
        "pages/3_Profile.py"
    ).read_text(encoding="utf-8")

    assert "if not product_policy.can_search:" in opportunities
    assert "product_mode_policy(product_state).can_mutate" in sources
    assert "product_mode_policy(product_state).can_mutate" in profile


def test_dashboard_and_interviews_have_read_only_write_gates():
    dashboard = Path("app.py").read_text(
        encoding="utf-8"
    )

    interviews = Path(
        "services/interview_preparation_ui.py"
    ).read_text(encoding="utf-8")

    assert "read_only: bool = False" in dashboard
    assert "disabled=read_only" in dashboard
    assert "and not read_only" in dashboard
    assert "read_only=read_only" in dashboard

    assert "read_only=False" in interviews
    assert "and not read_only" in interviews
    assert "if read_only:" in interviews
