from dataclasses import replace
from unittest.mock import Mock

import pytest

from models.career_update import CareerUpdate
from models.profile_interpretation import CoverageState, ProfileCapability
from services.candidate_profile_service import CandidateProfileService
from services.candidate_profile_updater import CandidateProfileUpdater
from services.profile_interpretation_service import ProfileInterpretationService
from services.profile_readiness_service import ProfileReadinessService
from services.structured_interpretation_validation import InterpretationValidationError
from tests.test_candidate_profile_updater import Interpreter, draft_from
from tests.test_profile_raw_source_sync import initial, update_event
from tests.test_workpilot_v1_onboarding_persistence import repo


def public_service(generator, repo, updates):
    return CandidateProfileService(
        snapshot_repository=generator.snapshot_repository,
        readiness_service=ProfileReadinessService(snapshots=generator.snapshot_repository,
                                                 onboarding=repo, updates=updates),
        generation_service=generator)


def forbid_raw_reads(monkeypatch, repo, updates):
    forbidden = Mock(side_effect=AssertionError("Materialized profiles must not reread RAW"))
    for method in ("get_onboarding", "list_work_experiences"):
        monkeypatch.setattr(repo, method, forbidden)
    monkeypatch.setattr(updates, "list_for_candidate", forbidden)
    monkeypatch.setattr("services.profile_readiness_service.load_confirmed_candidate_profile_input", forbidden)
    monkeypatch.setattr("services.profile_interpretation_service.load_confirmed_candidate_profile_input", forbidden)
    return forbidden


def test_v1_created_from_confirmed_raw_then_read_without_reconstruction(repo, monkeypatch):
    generator, v1, updates = initial(repo)
    assert v1.profile_version == 1 and v1.supersedes_version is None
    assert any(ref.startswith("professional_experience:") for ref in v1.source_refs)
    assert len(generator.llm_client.calls) == 1
    boundary = public_service(generator, repo, updates)
    forbidden = forbid_raw_reads(monkeypatch, repo, updates)
    monkeypatch.setattr(generator.llm_client, "generate", forbidden)
    assert boundary.current("a") == v1
    assert boundary.check_readiness("a").snapshot == v1
    assert boundary.refresh_current("a") == v1
    assert boundary.generate_snapshot("a") == v1
    assert ProfileInterpretationService(generator.snapshot_repository, generator).candidate_profile_from_onboarding(
        candidate_id="a", onboarding_repository=repo, career_update_repository=updates) == v1
    forbidden.assert_not_called()


def test_snapshot_event_chain_v1_v2_v3_never_reconstructs_raw(repo, monkeypatch):
    generator, v1, updates = initial(repo)
    snapshots = generator.snapshot_repository
    boundary = public_service(generator, repo, updates)
    forbidden = forbid_raw_reads(monkeypatch, repo, updates)
    first = update_event()
    draft2 = replace(draft_from(v1), capabilities=(
        *v1.capabilities, ProfileCapability("delivery", "Delivery", (first.source.ref,))))
    interpreter = Interpreter(draft2)
    updater = CandidateProfileUpdater(snapshots, interpreter)
    v2 = updater.update(v1, first)
    assert (v2.profile_version, v2.supersedes_version) == (2, 1)
    assert boundary.check_readiness("a").snapshot == v2

    second = replace(first, update_id="u2", description="Confirmed a new responsibility.",
                     source=replace(first.source, ref="career_update:u2"))
    interpreter.draft = replace(draft_from(v2), capabilities=(
        *v2.capabilities, ProfileCapability("coordination", "Coordination", (second.source.ref,))))
    v3 = updater.update(v2, second)
    assert (v3.profile_version, v3.supersedes_version) == (3, 2)
    assert interpreter.calls[1].candidate_profile == v2
    assert all(call.memory_projection is None and call.previous_checkpoint is None
               for call in interpreter.calls)
    assert {cap.capability_id for cap in v3.capabilities} >= {"delivery", "coordination"}
    assert v3.fact_coverage.languages is CoverageState.UNKNOWN
    assert not v3.confirmed_gaps
    assert boundary.current("a") == v3
    assert boundary.refresh_current("a") == v3
    assert boundary.generate_snapshot("a") == v3
    assert snapshots.candidate_version("a", 1) == v1
    assert snapshots.candidate_version("a", 2) == v2
    assert updater.update(v2, second) == v3
    assert len(interpreter.calls) == 2
    with pytest.raises(InterpretationValidationError, match="stale_input"):
        updater.update(v1, second)
    assert len(interpreter.calls) == 2
    forbidden.assert_not_called()


def test_new_raw_event_does_not_force_regeneration_or_change_evidence(repo):
    generator, v1, updates = initial(repo)
    boundary = public_service(generator, repo, updates)
    updates.save(CareerUpdate("new", "a", "project", "New source awaiting explicit update", "2026-10-03"))
    assert boundary.check_readiness("a").ready
    assert boundary.refresh_current("a") == v1
    assert generator.generate_snapshot("a") == v1
    assert generator.snapshot_repository.candidate_version("a", 2) is None
    assert len(generator.llm_client.calls) == 1
    assert "career_update:new" not in boundary.current("a").source_refs


def test_legacy_raw_sync_metadata_does_not_change_update_identity(repo):
    generator, v1, _ = initial(repo)
    interpreter = Interpreter(draft_from(v1))
    updater = CandidateProfileUpdater(generator.snapshot_repository, interpreter)
    event = update_event()
    v2 = updater.update(v1, event)
    assert updater.update(replace(v1, raw_source_signature="audit-only"), event) == v2
    assert len(interpreter.calls) == 1
    assert v2.raw_source_signature == ""


@pytest.mark.parametrize("invalid", ["schema", "owner"])
def test_invalid_snapshot_fails_closed_without_raw_rebuild(repo, monkeypatch, invalid):
    generator, v1, updates = initial(repo)
    invalid_snapshot = replace(v1, schema_version="unsupported") if invalid == "schema" else v1
    candidate_id = "a" if invalid == "schema" else "b"
    snapshots = Mock()
    snapshots.current_candidate.return_value = invalid_snapshot
    generation = Mock()
    readiness = ProfileReadinessService(snapshots=snapshots, onboarding=repo, updates=updates)
    boundary = CandidateProfileService(snapshot_repository=snapshots,
                                       readiness_service=readiness, generation_service=generation)
    forbidden = forbid_raw_reads(monkeypatch, repo, updates)
    assert boundary.check_readiness(candidate_id).status == "stale"
    assert boundary.refresh_current(candidate_id) is None
    assert not generation.mock_calls
    forbidden.assert_not_called()
