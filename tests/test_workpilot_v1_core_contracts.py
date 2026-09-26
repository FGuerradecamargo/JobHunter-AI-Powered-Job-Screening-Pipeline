from dataclasses import replace

import pytest

from models.hiring_case import RequirementImportance
from models.profile_interpretation import (
    CandidateFactCoverage,
    CandidateLanguage,
    CandidateLicence,
    CandidatePreference,
    CandidatePreferenceSemantic,
    CandidateProfileSnapshot,
    CandidateWorkAuthorization,
    CoverageState,
    CredentialStatus,
    InterpretationAuthority,
    InterpretedJobNeed,
    JobRequirementStatus,
    ProfileCheckpoint,
    RequirementRelevance,
    RequirementSubstitutability,
)


def source_profile(**changes):
    values = {
        "candidate_id": "candidate-a",
        "profile_version": 1,
        "memory_signature": "memory-1",
        "created_at": "2026-09-26T00:00:00+00:00",
        "source_refs": ("source:1",),
        "capabilities": (),
        "checkpoint": ProfileCheckpoint(current_position="Operations specialist"),
    }
    values.update(changes)
    return CandidateProfileSnapshot(**values)


def test_missing_finite_fact_is_not_authoritative_absence_by_default():
    profile = source_profile()
    assert profile.can_confirm_absence("languages") is False
    assert profile.can_confirm_absence("licences") is False
    assert profile.can_confirm_absence("work_authorizations") is False


@pytest.mark.parametrize("state", [CoverageState.UNKNOWN, CoverageState.PARTIAL])
def test_partial_or_unknown_coverage_never_confirms_absence(state):
    profile = source_profile(
        fact_coverage=CandidateFactCoverage(languages=state),
    )
    assert profile.can_confirm_absence("languages") is False


def test_confirmed_complete_coverage_can_support_an_absence_check():
    profile = source_profile(
        fact_coverage=CandidateFactCoverage(
            languages=CoverageState.CONFIRMED_COMPLETE,
        ),
    )
    assert profile.can_confirm_absence("languages") is True


def test_preference_allowed_set_and_constraint_are_distinct_semantics():
    base = dict(kind="work_mode", value="remote", evidence_refs=("source:1",))
    preference = CandidatePreference(
        **base, semantic=CandidatePreferenceSemantic.PREFERENCE
    )
    allowed = CandidatePreference(
        **base, semantic=CandidatePreferenceSemantic.ALLOWED_SET
    )
    constraint = CandidatePreference(
        **base, semantic=CandidatePreferenceSemantic.CONSTRAINT
    )
    assert len({preference.semantic, allowed.semantic, constraint.semantic}) == 3


def test_structured_language_and_licence_keep_unknown_details_unknown():
    language = CandidateLanguage(
        "English",
        evidence_refs=("source:1",),
    )
    licence = CandidateLicence(
        "Professional licence",
        evidence_refs=("source:1",),
    )
    assert language.proficiency == ""
    assert licence.status is CredentialStatus.UNKNOWN
    assert licence.jurisdiction == ""
    assert licence.expiry == ""


def test_structured_candidate_facts_must_be_source_backed():
    with pytest.raises(ValueError, match="source evidence"):
        CandidateLanguage("English")
    with pytest.raises(ValueError, match="source evidence"):
        CandidateLicence("Professional licence")
    with pytest.raises(ValueError, match="source evidence"):
        CandidateWorkAuthorization("Ireland")


def test_snapshot_rejects_structured_fact_that_cites_unknown_source():
    with pytest.raises(ValueError, match="source snapshot"):
        source_profile(
            languages=(CandidateLanguage("English", evidence_refs=("other",)),),
        )


def need(**changes):
    values = {
        "need_id": "need-1",
        "label": "Own regulated activity",
        "importance": RequirementImportance.CORE,
        "authority": InterpretationAuthority.EXPLICIT,
        "hard_fact_refs": ("fact-1",),
    }
    values.update(changes)
    return InterpretedJobNeed(**values)


def test_job_requirement_relevance_is_separate_from_requirement_status():
    item = need(
        requirement_status=JobRequirementStatus.PREFERRED,
        substitutability=RequirementSubstitutability.SUBSTITUTABLE,
    )
    assert item.performance_relevance is RequirementRelevance.CORE
    assert item.requirement_status is JobRequirementStatus.PREFERRED


def test_only_explicit_required_non_substitutable_need_has_strict_semantics():
    strict = need(
        requirement_status=JobRequirementStatus.REQUIRED,
        substitutability=RequirementSubstitutability.NON_SUBSTITUTABLE,
    )
    assert strict.is_non_substitutable_required is True

    assert replace(
        strict,
        authority=InterpretationAuthority.STRONGLY_IMPLIED,
    ).is_non_substitutable_required is False

    assert replace(
        strict,
        requirement_status=JobRequirementStatus.PREFERRED,
    ).is_non_substitutable_required is False

    assert replace(
        strict,
        substitutability=RequirementSubstitutability.SUBSTITUTABLE,
    ).is_non_substitutable_required is False


def test_preferred_need_cannot_be_declared_hard_blocker():
    with pytest.raises(ValueError, match="non-required"):
        need(
            hard_blocker=True,
            requirement_status=JobRequirementStatus.PREFERRED,
        )


def test_service_persists_all_structured_candidate_fields():
    from unittest.mock import Mock
    from models.candidate import Candidate
    from services.candidate_repository import CandidateRepository
    from models.profile_interpretation import CandidateProfileDraft, SourceEvidence
    from services.profile_interpretation_service import ProfileInterpretationService
    from services.profile_snapshot_repository import ProfileSnapshotRepository

    draft = CandidateProfileDraft(
        capabilities=(), checkpoint=ProfileCheckpoint(current_position="Operations"),
        structured_preferences=(CandidatePreference("work_mode", "remote", CandidatePreferenceSemantic.ALLOWED_SET, ("source:1",)),),
        languages=(CandidateLanguage("English", evidence_refs=("source:1",)),),
        licences=(CandidateLicence("Licence", status=CredentialStatus.ACTIVE, evidence_refs=("source:1",)),),
        work_authorizations=(CandidateWorkAuthorization("Ireland", evidence_refs=("source:1",)),),
        fact_coverage=CandidateFactCoverage(languages=CoverageState.CONFIRMED_COMPLETE, licences=CoverageState.PARTIAL),
    )
    CandidateRepository().save(Candidate("candidate-a", "Synthetic", "", "", ""))
    repository = ProfileSnapshotRepository()
    interpreter = Mock()
    interpreter.build_candidate_profile.return_value = draft
    profile = ProfileInterpretationService(repository, interpreter).candidate_profile(
        candidate_id="candidate-a", memory_signature="memory-1", memory_payload={},
        source_evidence=(SourceEvidence("source:1", "confirmed_input", "Synthetic facts"),),
    )
    restored = repository.current_candidate("candidate-a")
    assert restored == profile
    for name in ("structured_preferences", "languages", "licences", "work_authorizations", "fact_coverage"):
        assert getattr(restored, name) == getattr(draft, name)
    assert restored.languages[0].evidence_refs == ("source:1",)
    assert restored.licences[0].status is CredentialStatus.ACTIVE
    assert restored.structured_preferences[0].semantic is CandidatePreferenceSemantic.ALLOWED_SET
    assert restored.can_confirm_absence("languages") is True
    assert restored.can_confirm_absence("licences") is False


def test_legacy_candidate_snapshot_defaults_to_unknown_coverage():
    import json
    from dataclasses import asdict
    from services.profile_snapshot_repository import _candidate_from_json

    data = asdict(source_profile())
    for name in ("structured_preferences", "languages", "licences", "work_authorizations", "fact_coverage"):
        del data[name]
    restored = _candidate_from_json(json.dumps(data))
    assert restored == source_profile()
    assert restored.fact_coverage.languages is CoverageState.UNKNOWN


def test_job_snapshot_round_trip_restores_requirement_enums():
    import json
    from dataclasses import asdict
    from models.profile_interpretation import AIJobProfileSnapshot
    from services.profile_snapshot_repository import _job_from_json

    profile = AIJobProfileSnapshot("job-a", 1, "signature", "2026-09-26", (
        need(requirement_status=JobRequirementStatus.REQUIRED,
             substitutability=RequirementSubstitutability.NON_SUBSTITUTABLE),
    ))
    restored = _job_from_json(json.dumps(asdict(profile)))
    assert restored == profile
    assert restored.needs[0].is_non_substitutable_required is True
    data = asdict(profile)
    del data["needs"][0]["requirement_status"]
    del data["needs"][0]["substitutability"]
    legacy = _job_from_json(json.dumps(data))
    assert legacy.needs[0].requirement_status is JobRequirementStatus.UNKNOWN
    assert legacy.needs[0].substitutability is RequirementSubstitutability.UNKNOWN
