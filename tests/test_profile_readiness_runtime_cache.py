from types import SimpleNamespace
from unittest.mock import Mock

import services.profile_readiness_service as module
from services.profile_readiness_service import (
    ProfileReadiness,
    profile_readiness,
)


def test_same_candidate_is_checked_once_per_rerun(
    monkeypatch,
):
    context = SimpleNamespace(
        cursors=object()
    )

    monkeypatch.setattr(
        module,
        "get_script_run_ctx",
        lambda: context,
    )

    service = Mock()
    expected = ProfileReadiness(
        "missing"
    )
    service.check.return_value = expected

    monkeypatch.setattr(
        module,
        "ProfileReadinessService",
        lambda: service,
    )

    first = profile_readiness(
        "candidate-a"
    )
    second = profile_readiness(
        "candidate-a"
    )

    assert first is expected
    assert second is expected

    service.check.assert_called_once_with(
        "candidate-a"
    )


def test_new_rerun_revalidates_profile_readiness(
    monkeypatch,
):
    context = SimpleNamespace(
        cursors=object()
    )

    monkeypatch.setattr(
        module,
        "get_script_run_ctx",
        lambda: context,
    )

    service = Mock()
    service.check.return_value = (
        ProfileReadiness("ready")
    )

    monkeypatch.setattr(
        module,
        "ProfileReadinessService",
        lambda: service,
    )

    profile_readiness(
        "candidate-a"
    )

    assert service.check.call_count == 1

    # Streamlit replaces cursors on the next script run.
    context.cursors = object()

    profile_readiness(
        "candidate-a"
    )

    assert service.check.call_count == 2


def test_candidates_are_cached_independently(
    monkeypatch,
):
    context = SimpleNamespace(
        cursors=object()
    )

    monkeypatch.setattr(
        module,
        "get_script_run_ctx",
        lambda: context,
    )

    service = Mock()
    service.check.side_effect = [
        ProfileReadiness("missing"),
        ProfileReadiness("ready"),
    ]

    monkeypatch.setattr(
        module,
        "ProfileReadinessService",
        lambda: service,
    )

    profile_readiness("candidate-a")
    profile_readiness("candidate-b")
    profile_readiness("candidate-a")
    profile_readiness("candidate-b")

    assert service.check.call_count == 2


def test_without_streamlit_context_no_runtime_cache_is_used(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "get_script_run_ctx",
        lambda: None,
    )

    service = Mock()
    service.check.return_value = (
        ProfileReadiness("missing")
    )

    monkeypatch.setattr(
        module,
        "ProfileReadinessService",
        lambda: service,
    )

    profile_readiness("candidate-a")
    profile_readiness("candidate-a")

    assert service.check.call_count == 2


def test_unavailable_result_is_cached_only_for_current_rerun(
    monkeypatch,
):
    context = SimpleNamespace(
        cursors=object()
    )

    monkeypatch.setattr(
        module,
        "get_script_run_ctx",
        lambda: context,
    )

    service = Mock()
    service.check.side_effect = (
        RuntimeError("private failure")
    )

    monkeypatch.setattr(
        module,
        "ProfileReadinessService",
        lambda: service,
    )

    first = profile_readiness(
        "candidate-a"
    )
    second = profile_readiness(
        "candidate-a"
    )

    assert first.status == "unavailable"
    assert second.status == "unavailable"
    assert service.check.call_count == 1

    context.cursors = object()

    third = profile_readiness(
        "candidate-a"
    )

    assert third.status == "unavailable"
    assert service.check.call_count == 2
