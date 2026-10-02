import ast
from dataclasses import asdict, fields, replace
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from models.candidate_profile_update import CandidateProfileUpdateInput
from models.candidate import Candidate
from models.profile_interpretation import (
    CandidateProfileDraft, CandidateProfileSnapshot, ProfileCapability, ProfileCheckpoint,
    CandidateFactCoverage, CoverageState, CandidateLanguage,
)
from models.source_reference import RegisteredSourceRef, SourceRefClass
from models.structured_interpretation import InterpretationOperation, ValidationStatus
from services.candidate_profile_updater import CandidateProfileUpdater
from services.candidate_repository import CandidateRepository
from services.fixture_structured_interpreter import validate_response
from services.profile_snapshot_repository import ProfileSnapshotRepository, _candidate_from_json
from services.structured_interpretation_validation import InterpretationValidationError
from tests.test_v1_runtime_candidate_profile import Client, service
from tests.test_workpilot_v1_onboarding_persistence import repo


def provenance(ref, kind="professional_experience", usable=True):
    return RegisteredSourceRef(ref, SourceRefClass.CAREER_MEMORY_SOURCE, "a", kind, usable)


@pytest.fixture
def base():
    return CandidateProfileSnapshot(
        candidate_id="a", profile_version=1, memory_signature="initial", created_at="2026-10-01",
        source_refs=("opaque-evidence", "opaque-preference"),
        source_registry=(provenance("opaque-evidence"),
                         provenance("opaque-preference", "candidate_preference", False)),
        capabilities=(ProfileCapability("cap", "Investigation", ("opaque-evidence",)),),
        checkpoint=ProfileCheckpoint("Investigator", proven_strengths=("Investigation",)),
        objectives=("Grow professionally",), evidence_gaps=("Need more examples",),
    )


def event(kind="career_update", usable=True):
    return CandidateProfileUpdateInput("u1", "a", "confirmed_update", "Completed a professional project.",
        provenance("career_update:u1", kind, usable), "2026-10-02")


def draft_from(base):
    return CandidateProfileDraft(**{field.name: getattr(base, field.name)
                                   for field in fields(CandidateProfileDraft)})


class Interpreter:
    def __init__(self, draft):
        self.draft = draft
        self.calls = []

    def interpret(self, request):
        self.calls.append(request)
        return validate_response(request, asdict(self.draft),
                                 produced_at="2026-10-02", interpreter_version="offline")


def prepared(base, draft=None):
    CandidateRepository().save(Candidate("a", "Fixture", "", "", ""))
    repository = ProfileSnapshotRepository()
    repository.save_candidate(base)
    interpreter = Interpreter(draft or draft_from(base))
    return repository, interpreter, CandidateProfileUpdater(repository, interpreter, clock=lambda: "2026-10-02")


def test_provenance_roundtrip_and_legacy_loading(base):
    repository, _, _ = prepared(base)
    assert repository.current_candidate("a") == base
    entries = repository.current_candidate("a").source_registry
    assert entries[0].usable_evidence is True
    assert entries[1].source_type == "candidate_preference"
    assert entries[1].usable_evidence is False
    raw = asdict(base)
    del raw["source_registry"]
    legacy = _candidate_from_json(json.dumps(raw))
    assert legacy.source_refs == base.source_refs
    assert legacy.source_registry == ()


def test_update_preserves_state_lineage_provenance_and_reuses_same_pair(base, monkeypatch):
    import services.candidate_profile_source as raw_source
    loader = Mock(side_effect=AssertionError("Must not reconstruct raw sources"))
    monkeypatch.setattr(raw_source, "load_confirmed_candidate_profile_input", loader)
    draft = replace(draft_from(base), capabilities=(
        *base.capabilities, ProfileCapability("new", "Delivery", ("career_update:u1",))))
    repository, interpreter, updater = prepared(base, draft)
    updated = updater.update(base, event())
    assert updated.profile_version == 2 and updated.supersedes_version == 1
    assert updated.candidate_id == "a"
    assert updated.source_refs == tuple(sorted((*base.source_refs, "career_update:u1")))
    assert updated.source_registry == (*base.source_registry, event().source)
    assert updated.objectives == base.objectives
    assert updated.evidence_gaps == base.evidence_gaps
    assert repository.candidate_version("a", 1) == base
    assert repository.current_candidate("a") == updated
    assert updater.update(base, event()) == updated
    assert len(interpreter.calls) == 1
    request = interpreter.calls[0]
    assert request.operation is InterpretationOperation.UPDATE_CANDIDATE_PROFILE
    assert request.candidate_profile == base and request.candidate_update == event()
    assert request.memory_projection is None and request.previous_checkpoint is None
    loader.assert_not_called()


def test_candidate_mismatch_precedes_provider_and_persistence(base):
    repository, interpreter = Mock(), Mock()
    wrong = replace(event(), candidate_id="b", source=replace(event().source, owner_id="b"))
    with pytest.raises(InterpretationValidationError, match="invalid_scope"):
        CandidateProfileUpdater(repository, interpreter).update(base, wrong)
    assert not repository.mock_calls and not interpreter.mock_calls


def test_legacy_missing_authority_fails_before_provider(base):
    repository, interpreter = Mock(), Mock()
    with pytest.raises(InterpretationValidationError, match="unknown_ref"):
        CandidateProfileUpdater(repository, interpreter).update(replace(base, source_registry=()), event())
    assert not repository.mock_calls and not interpreter.mock_calls


@pytest.mark.parametrize("ref", ["invented:1", "opaque-preference", "checkpoint:1"])
def test_unknown_preference_and_checkpoint_refs_cannot_support_capabilities(base, ref):
    draft = replace(draft_from(base), capabilities=(ProfileCapability("new", "Claim", (ref,)),))
    repository, _, updater = prepared(base, draft)
    with pytest.raises(InterpretationValidationError):
        updater.update(base, event())
    assert repository.current_candidate("a") == base


def test_new_preference_event_cannot_support_capability(base):
    draft = replace(draft_from(base), capabilities=(ProfileCapability("new", "Claim", ("career_update:u1",)),))
    repository, _, updater = prepared(base, draft)
    with pytest.raises(InterpretationValidationError):
        updater.update(base, event("candidate_preference", False))
    assert repository.current_candidate("a") == base


def test_preference_event_can_update_direction_without_changing_evidence(base):
    draft = replace(draft_from(base), objectives=("New direction",))
    _, _, updater = prepared(base, draft)
    updated = updater.update(base, event("candidate_preference", False))
    assert updated.objectives == ("New direction",)
    assert updated.capabilities == base.capabilities
    assert updated.source_registry[-1].usable_evidence is False


@pytest.mark.parametrize("checkpoint_gap", [True, False])
def test_ordinary_update_cannot_create_confirmed_absence(base, checkpoint_gap):
    draft = draft_from(base)
    draft = (replace(draft, checkpoint=replace(draft.checkpoint, confirmed_gaps=("Missing skill",)))
             if checkpoint_gap else replace(draft, confirmed_gaps=("Missing skill",)))
    repository, _, updater = prepared(base, draft)
    with pytest.raises(InterpretationValidationError):
        updater.update(base, event())
    assert repository.current_candidate("a") == base


def test_stale_base_does_not_call_provider_again(base):
    repository, interpreter, updater = prepared(base)
    updater.update(base, event())
    newer_event = replace(event(), update_id="u2", source=provenance("career_update:u2", "career_update"))
    with pytest.raises(InterpretationValidationError, match="stale_input"):
        updater.update(base, newer_event)
    assert len(interpreter.calls) == 1
    assert repository.current_candidate("a").profile_version == 2


@pytest.mark.parametrize("same_update", [True, False])
def test_concurrent_writer_reuses_same_update_but_never_overwrites_other(base, monkeypatch, same_update):
    repository, _, updater = prepared(base)
    original_save = repository.save_candidate
    def race(profile):
        winner = profile if same_update else replace(profile, memory_signature="another-update")
        original_save(winner)
        original_save(profile)
    monkeypatch.setattr(repository, "save_candidate", race)
    if same_update:
        assert updater.update(base, event()) == repository.current_candidate("a")
    else:
        with pytest.raises(InterpretationValidationError, match="stale_input"):
            updater.update(base, event())
        assert repository.current_candidate("a").memory_signature == "another-update"
    assert repository.current_candidate("a").profile_version == 2


@pytest.mark.parametrize("name", ["update_id", "candidate_id", "update_type", "description"])
def test_update_input_rejects_blank_fields(name):
    with pytest.raises(ValueError):
        replace(event(), **{name: "  "})


def test_updater_has_no_raw_source_or_legacy_dependencies():
    source = Path("services/candidate_profile_updater.py").read_text()
    for forbidden in ("CandidateOnboardingRepository", "WorkExperience", "CareerUpdateRepository",
                      "CandidateRepository", "ProfileReadinessService", "load_confirmed_candidate_profile_input"):
        assert forbidden not in source
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.ImportFrom) and node.module in {
        "services.candidate_profile_source", "services.profile_interpretation_service",
        "services.candidate_profile_generation_service"} for node in ast.walk(tree))


def test_initial_generation_persists_authoritative_source_types(repo):
    generator = service(repo, Client())
    snapshot = generator.generate_snapshot("a")
    stored = generator.snapshot_repository.current_candidate("a")
    assert stored == snapshot
    assert {item.ref for item in stored.source_registry} == set(stored.source_refs)
    assert any(item.source_type == "professional_experience" and item.usable_evidence
               for item in stored.source_registry)
    assert any(item.source_type == "candidate_preference" and not item.usable_evidence
               for item in stored.source_registry)


def test_untrusted_adapter_cannot_skip_output_validation(base):
    repository, interpreter, updater = prepared(base)
    original = interpreter.interpret
    def forged(request):
        result = original(request)
        bad = replace(draft_from(base), capabilities=(
            ProfileCapability("bad", "Claim", ("opaque-preference",)),))
        return replace(result, output_payload=bad, validation_status=ValidationStatus.ACCEPTED)
    interpreter.interpret = forged
    with pytest.raises(InterpretationValidationError, match="wrong_source_class"):
        updater.update(base, event())
    assert repository.current_candidate("a") == base


def test_preference_cannot_self_declare_evidence_authority(base):
    repository, interpreter = Mock(), Mock()
    with pytest.raises(InterpretationValidationError, match="wrong_source_class"):
        CandidateProfileUpdater(repository, interpreter).update(base, event("candidate_preference", True))
    assert not repository.mock_calls and not interpreter.mock_calls


def test_ordinary_update_cannot_infer_exhaustive_coverage(base):
    draft = replace(draft_from(base),
                    fact_coverage=CandidateFactCoverage(languages=CoverageState.CONFIRMED_COMPLETE))
    repository, _, updater = prepared(base, draft)
    with pytest.raises(InterpretationValidationError):
        updater.update(base, event())
    assert repository.current_candidate("a") == base


def test_structured_facts_cannot_cite_invented_refs(base):
    draft = replace(draft_from(base), languages=(CandidateLanguage("English", evidence_refs=("invented",)),))
    repository, _, updater = prepared(base, draft)
    with pytest.raises(InterpretationValidationError):
        updater.update(base, event())
    assert repository.current_candidate("a") == base


def test_existing_confirmed_gaps_are_preserved_not_reconstructed(base):
    base = replace(base, confirmed_gaps=("Existing confirmed gap",),
                   checkpoint=replace(base.checkpoint, confirmed_gaps=("Existing confirmed gap",)))
    _, _, updater = prepared(base)
    updated = updater.update(base, event())
    assert updated.confirmed_gaps == base.confirmed_gaps
    assert updated.checkpoint.confirmed_gaps == base.checkpoint.confirmed_gaps
