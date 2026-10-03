import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from models.profile_interpretation import CandidateProfileSnapshot
from services.candidate_profile_generation_service import CandidateProfileGenerationService
from services.candidate_profile_service import CandidateProfileService
from services.profile_readiness_service import ProfileReadiness
from tests.test_v1_runtime_candidate_profile import Client, service
from tests.test_workpilot_v1_onboarding_persistence import repo


def test_current_returns_existing_candidate_snapshot_or_none():
    snapshots, readiness, generation = Mock(), Mock(), Mock()
    boundary = CandidateProfileService(snapshot_repository=snapshots,
        readiness_service=readiness, generation_service=generation)
    for value in (Mock(spec=CandidateProfileSnapshot), None):
        snapshots.current_candidate.return_value = value
        assert boundary.current("candidate-a") is value
        snapshots.current_candidate.assert_called_with("candidate-a")
    assert not readiness.mock_calls
    assert not generation.mock_calls


@pytest.mark.parametrize("status", ["ready", "stale", "missing", "no_evidence", "unavailable"])
def test_readiness_is_delegated_unchanged(status):
    snapshots, readiness, generation = Mock(), Mock(), Mock()
    result = ProfileReadiness(status)
    readiness.check.return_value = result
    boundary = CandidateProfileService(snapshot_repository=snapshots,
        readiness_service=readiness, generation_service=generation)
    assert boundary.check_readiness("candidate-a") is result
    readiness.check.assert_called_once_with("candidate-a")
    assert not snapshots.mock_calls
    assert not generation.mock_calls


def test_boundary_generates_authoritative_snapshot_without_legacy_save(repo, monkeypatch):
    client = Client()
    generator = service(repo, client)
    previous = generator.candidate_repository.get("a")
    save = Mock(side_effect=AssertionError("Canonical generation must not save legacy projection"))
    monkeypatch.setattr(generator.candidate_repository, "save", save)
    generation = Mock(wraps=generator)
    boundary = CandidateProfileService(snapshot_repository=generator.snapshot_repository,
        readiness_service=Mock(), generation_service=generation)
    snapshot = boundary.generate_snapshot("a")
    assert isinstance(snapshot, CandidateProfileSnapshot)
    generation.generate_snapshot.assert_called_once_with("a")
    assert boundary.current("a") == snapshot
    assert boundary.current("b") is None
    assert boundary.generate_snapshot("a") == snapshot
    assert len(client.calls) == 1
    assert generator.candidate_repository.get("a") == previous
    save.assert_not_called()


def test_legacy_generation_uses_canonical_path_and_saves_projection(repo, monkeypatch):
    generator = service(repo, Client())
    snapshot = generator.generate_snapshot("a")
    canonical = Mock(return_value=snapshot)
    monkeypatch.setattr(generator, "generate_snapshot", canonical)
    candidate = generator.generate("a", "Fixture")
    canonical.assert_called_once_with("a")
    assert generator.candidate_repository.get("a") == candidate
    assert candidate.name == "Fixture"
    assert candidate.professional_summary == snapshot.checkpoint.current_position
    assert candidate.current_level == snapshot.seniority
    assert candidate.proven_capabilities == [c.label for c in snapshot.capabilities if not c.transferable]
    assert candidate.transferable_capabilities == [c.label for c in snapshot.capabilities if c.transferable]
    assert candidate.strengths == list(snapshot.checkpoint.proven_strengths)
    assert candidate.development_areas == list(snapshot.evidence_gaps)
    assert candidate.spoken_languages == list(generator.onboarding_repository.get_onboarding("a").spoken_languages)


def test_missing_onboarding_still_fails_before_interpretation():
    onboarding, candidate, updates, snapshots, client = (Mock() for _ in range(5))
    onboarding.get_onboarding.return_value = None
    snapshots.current_candidate.return_value = None
    generator = CandidateProfileGenerationService(client, onboarding, candidate, updates,
                                                  snapshot_repository=snapshots)
    for operation in (lambda: generator.generate_snapshot("a"), lambda: generator.generate("a", "Name")):
        with pytest.raises(ValueError, match="Candidate onboarding was not found"):
            operation()
    assert snapshots.current_candidate.call_count == 2
    snapshots.save_candidate.assert_not_called()
    for dependency in (candidate, updates, client):
        assert not dependency.mock_calls


def test_candidate_only_public_architecture_and_onboarding_port():
    source = Path("services/candidate_profile_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == {"models.profile_interpretation", "services.candidate_profile_generation_service",
                       "services.profile_readiness_service", "services.profile_snapshot_repository"}
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert methods == {"__init__", "current", "check_readiness", "generate_snapshot", "refresh_current"}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert attributes == {"_snapshots", "_readiness", "_generation", "current_candidate", "check", "generate_snapshot",
                          "check_readiness", "backfill_missing", "status", "snapshot", "ready"}
    for forbidden in ("JobProfile", "HiringCase", "models.candidate", "match", "job_"):
        assert forbidden not in source
    onboarding = Path("components/onboarding.py").read_text(encoding="utf-8")
    assert "from services.profile_gateway import ProfileGateway" in onboarding
    for forbidden in ("CandidateProfileService", "CandidateProfileGenerationService", "ProfileSnapshotRepository",
                      "ProfileReadinessService", "CandidateRepository"):
        assert forbidden not in onboarding


def test_readiness_exception_is_safe_and_unavailable():
    readiness = Mock()
    readiness.check.side_effect = RuntimeError("private evidence")
    boundary = CandidateProfileService(snapshot_repository=Mock(),
        readiness_service=readiness, generation_service=Mock())
    result = boundary.check_readiness("a")
    assert result == ProfileReadiness("unavailable")
    assert "private evidence" not in result.message


@pytest.mark.parametrize("status", ["missing", "stale", "unavailable", "ready", "no_evidence"])
def test_refresh_routes_only_eligible_states(status):
    readiness, generation, snapshots = Mock(), Mock(), Mock()
    snapshot = Mock(spec=CandidateProfileSnapshot)
    readiness.check.return_value = ProfileReadiness(status, snapshot if status == "ready" else None)
    boundary = CandidateProfileService(snapshot_repository=snapshots,
        readiness_service=readiness, generation_service=generation)
    result = boundary.refresh_current("a")
    if status == "missing":
        readiness.backfill_missing.assert_called_once_with("a", generation)
        assert result is readiness.backfill_missing.return_value
        generation.generate_snapshot.assert_not_called()
    else:
        assert result is (snapshot if status == "ready" else None)
        readiness.backfill_missing.assert_not_called()
        generation.generate_snapshot.assert_not_called()
    assert not snapshots.mock_calls


def test_refresh_readiness_exception_does_not_generate_or_backfill():
    readiness, generation, snapshots = Mock(), Mock(), Mock()
    readiness.check.side_effect = RuntimeError("private evidence")
    boundary = CandidateProfileService(snapshot_repository=snapshots,
        readiness_service=readiness, generation_service=generation)

    assert boundary.refresh_current("a") is None

    readiness.check.assert_called_once_with("a")
    readiness.backfill_missing.assert_not_called()
    assert not generation.mock_calls
    assert not snapshots.mock_calls
