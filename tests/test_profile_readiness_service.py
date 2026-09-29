from dataclasses import replace
from unittest.mock import Mock

import pytest

from models.candidate_onboarding import CandidateOnboarding
from services.candidate_repository import CandidateRepository
from services.profile_readiness_service import ProfileReadinessService, profile_readiness
from services.profile_snapshot_repository import ProfileSnapshotRepository
from tests.test_workpilot_v1_onboarding_persistence import repo
from tests.test_v1_runtime_candidate_profile import Client, service


def test_legacy_summary_is_not_ready_and_backfill_preserves_candidate(repo):
    generator = service(repo, Client())
    candidates = CandidateRepository()
    original = replace(candidates.get("a"), current_role="Legacy role", professional_summary="Legacy summary")
    candidates.save(original)
    gate = ProfileReadinessService()
    assert gate.check("a").status == "missing"
    snapshot = gate.backfill_missing("a", generator)
    assert gate.check("a").ready
    assert gate.backfill_missing("a", generator) == snapshot
    assert len(generator.llm_client.calls) == 1
    assert candidates.get("a") == original
    assert gate.check("b").status == "no_evidence"
    assert ProfileSnapshotRepository().current_candidate("b") is None


def test_changed_evidence_is_stale_and_backfill_never_replaces_history(repo):
    generator = service(repo, Client())
    gate = ProfileReadinessService()
    first = gate.backfill_missing("a", generator)
    repo.save_onboarding(CandidateOnboarding("a", desired_next_work="New direction"))
    assert gate.check("a").status == "stale"
    assert not gate.check("a").ready
    assert gate.backfill_missing("a", generator) == first
    assert len(generator.llm_client.calls) == 1
    assert gate.snapshots.candidate_version("a", 1) == first


def test_backfill_without_confirmed_evidence_cannot_call_ai(repo):
    interpreter = Mock()
    with pytest.raises(ValueError, match="Confirmed"):
        ProfileReadinessService().backfill_missing("a", interpreter)
    interpreter.build_candidate_profile.assert_not_called()


def test_failed_backfill_preserves_candidate_and_can_retry(repo):
    generator = service(repo, Client())
    before = CandidateRepository().get("a")
    gate = ProfileReadinessService()
    broken = Mock()
    broken.build_candidate_profile.side_effect = RuntimeError("private failure")
    with pytest.raises(RuntimeError):
        gate.backfill_missing("a", broken)
    assert gate.snapshots.current_candidate("a") is None
    assert CandidateRepository().get("a") == before
    assert gate.backfill_missing("a", generator)
    assert gate.check("a").ready


def test_readiness_fails_closed_without_error_content(monkeypatch):
    import services.profile_readiness_service as module
    broken = Mock()
    broken.check.side_effect = RuntimeError("secret")
    monkeypatch.setattr(module, "ProfileReadinessService", lambda: broken)
    result = profile_readiness("a")
    assert not result.ready
    assert "secret" not in result.message
