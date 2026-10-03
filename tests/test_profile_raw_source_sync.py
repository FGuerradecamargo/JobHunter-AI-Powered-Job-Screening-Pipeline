from dataclasses import asdict, replace
import json
from unittest.mock import Mock

import pytest

from models.career_update import CareerUpdate
from models.candidate_profile_update import CandidateProfileSourceSync, CandidateProfileUpdateInput
from models.source_reference import RegisteredSourceRef, SourceRefClass
from services.candidate_profile_source import load_confirmed_candidate_profile_input
from services.candidate_profile_updater import CandidateProfileUpdater
from services.career_update_repository import CareerUpdateRepository
from services.profile_readiness_service import ProfileReadinessService
from services.profile_snapshot_repository import _candidate_from_json
from services.structured_interpretation_validation import InterpretationValidationError
from tests.test_candidate_profile_updater import Interpreter, draft_from
from tests.test_v1_runtime_candidate_profile import Client, service
from tests.test_workpilot_v1_onboarding_persistence import repo


def initial(repo):
    generator = service(repo, Client())
    return generator, generator.generate_snapshot("a"), CareerUpdateRepository()


def raw_state(repo, updates):
    return load_confirmed_candidate_profile_input("a", repo, updates)[0]


def update_event():
    return CandidateProfileUpdateInput(
        "u1", "a", "project", "Completed a project.",
        RegisteredSourceRef("career_update:u1", SourceRefClass.CAREER_MEMORY_SOURCE,
                            "a", "career_update", True), "2026-10-03")


def persist_event(updates, event):
    updates.save(CareerUpdate(event.update_id, event.candidate_id, event.update_type,
                              event.description, event.created_at))


def test_initial_signature_roundtrip_and_ready(repo):
    generator, profile, updates = initial(repo)
    assert profile.raw_source_signature == raw_state(repo, updates).source_signature
    assert generator.snapshot_repository.current_candidate("a") == profile
    assert ProfileReadinessService().check("a").ready


@pytest.mark.parametrize("mutation", ["edit_same_id", "add", "delete"])
def test_raw_mutation_not_incorporated_is_stale(repo, mutation):
    generator, _, updates = initial(repo)
    event = update_event()
    persist_event(updates, event)
    profile = generator.generate_snapshot("a")
    before_refs = profile.source_refs
    if mutation == "edit_same_id":
        persist_event(updates, replace(event, description="Different project content."))
        _, sources = load_confirmed_candidate_profile_input("a", repo, updates)
        assert {item.ref for item in sources} == set(before_refs)
    elif mutation == "add":
        updates.save(CareerUpdate("u2", "a", "project", "Another project.", "2026-10-03"))
    else:
        assert updates.delete("u1", "a")
    assert raw_state(repo, updates).source_signature != profile.raw_source_signature
    assert ProfileReadinessService().check("a").status == "stale"


@pytest.mark.parametrize("supply_sync", [True, False])
def test_incremental_update_sync_is_explicit_and_separate(repo, monkeypatch, supply_sync):
    generator, base, updates = initial(repo)
    event = update_event()
    persist_event(updates, event)
    authoritative = raw_state(repo, updates).source_signature
    sync = CandidateProfileSourceSync("a", event.update_id, authoritative) if supply_sync else None
    interpreter = Interpreter(draft_from(base))
    updater = CandidateProfileUpdater(generator.snapshot_repository, interpreter)
    with monkeypatch.context() as patch:
        loader = Mock(side_effect=AssertionError("Updater must not read raw history"))
        patch.setattr("services.candidate_profile_source.load_confirmed_candidate_profile_input", loader)
        result = updater.update(base, event, source_sync=sync)
        assert updater.update(base, event, source_sync=sync) == result
        loader.assert_not_called()
    assert len(interpreter.calls) == 1
    assert result.profile_version == base.profile_version + 1
    assert result.supersedes_version == base.profile_version
    assert result.memory_signature != authoritative
    assert result.raw_source_signature == (authoritative if supply_sync else "")
    assert generator.snapshot_repository.current_candidate("a") == result
    readiness = ProfileReadinessService().check("a")
    assert readiness.status == ("ready" if supply_sync else "stale")
    if supply_sync:
        assert readiness.snapshot == result


def test_legacy_snapshot_does_not_infer_raw_sync_from_old_identity(repo):
    generator, profile, _ = initial(repo)
    raw = asdict(profile)
    del raw["raw_source_signature"]
    legacy = _candidate_from_json(json.dumps(raw))
    assert legacy.raw_source_signature == ""
    assert legacy.memory_signature == profile.raw_source_signature
    repository = Mock()
    repository.current_candidate.return_value = legacy
    gate = ProfileReadinessService(snapshots=repository, onboarding=repo, updates=CareerUpdateRepository())
    assert gate.check("a").status == "stale"
    repository.current_candidate.assert_called_once_with("a")
    repository.candidate_for_readiness.assert_not_called()


def test_newer_unsynchronized_snapshot_cannot_be_hidden_by_historical_match(repo):
    generator, base, _ = initial(repo)
    newer = replace(base, profile_version=2, supersedes_version=1,
                    memory_signature="incremental", raw_source_signature="")
    generator.snapshot_repository.save_candidate(newer)
    # Raw history still matches v1, but readiness must assess current v2.
    assert ProfileReadinessService().check("a").status == "stale"


@pytest.mark.parametrize("candidate_id,update_id", [("b", "u1"), ("a", "other")])
def test_sync_binding_mismatch_rejected_before_provider_or_storage(repo, candidate_id, update_id):
    _, base, _ = initial(repo)
    repository, interpreter = Mock(), Mock()
    with pytest.raises(InterpretationValidationError, match="invalid_scope"):
        CandidateProfileUpdater(repository, interpreter).update(
            base, update_event(), source_sync=CandidateProfileSourceSync(candidate_id, update_id, "raw"))
    assert not repository.mock_calls and not interpreter.mock_calls


def test_failed_update_cannot_persist_sync_claim(repo):
    generator, base, updates = initial(repo)
    event = update_event()
    persist_event(updates, event)
    interpreter = Mock()
    interpreter.interpret.side_effect = RuntimeError("Offline failure")
    with pytest.raises(RuntimeError):
        CandidateProfileUpdater(generator.snapshot_repository, interpreter).update(
            base, event, source_sync=CandidateProfileSourceSync("a", event.update_id,
                                                              raw_state(repo, updates).source_signature))
    assert generator.snapshot_repository.current_candidate("a") == base
    assert ProfileReadinessService().check("a").status == "stale"


@pytest.mark.parametrize("name", ["candidate_id", "update_id", "raw_source_signature"])
def test_sync_attestation_rejects_blank_fields(name):
    with pytest.raises(ValueError):
        replace(CandidateProfileSourceSync("a", "u1", "raw"), **{name: " "})
