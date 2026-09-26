from dataclasses import replace
import pytest

from models.hiring_case import (
    HiringCaseClassification,
    OpportunitySignal,
    OpportunitySignalKind,
    OpportunitySignalState,
    RequirementEvidenceState,
    RequirementImportance,
)
from models.job_profile import JobProfile
from models.profile_interpretation import (
    AIJobProfileSnapshot,
    CandidateProfileSnapshot,
    HiringCaseInterpretation,
    InterpretationAuthority,
    InterpretedJobNeed,
    JobRequirementStatus,
    ProfileCapability,
    ProfileCheckpoint,
    RequirementLink,
    RequirementSubstitutability,
)
from services.authoritative_hiring_case_service import (
    AuthoritativeHiringCaseService,
)
from services.job_hard_facts import build_job_hard_facts


class FakeInterpreter:
    def analyze_hiring_case(self, *, candidate_profile, job_profile):
        return HiringCaseInterpretation(
            requirement_links=(
                RequirementLink(
                    "need-1",
                    RequirementEvidenceState.PROVEN,
                    ("experience:1",),
                    "Direct source-backed evidence.",
                    True,
                ),
            ),
            opportunity_signals=(
                OpportunitySignal(
                    OpportunitySignalKind.CAREER_DIRECTION,
                    OpportunitySignalState.POSITIVE,
                    RequirementImportance.CORE,
                    "Aligned with stated direction.",
                ),
            ),
        )


def candidate():
    return CandidateProfileSnapshot(
        candidate_id="candidate-a",
        profile_version=3,
        memory_signature="candidate-signature",
        created_at="2026-09-26T00:00:00+00:00",
        source_refs=("experience:1",),
        capabilities=(
            ProfileCapability(
                "cap-1",
                "Investigation",
                ("experience:1",),
            ),
        ),
        checkpoint=ProfileCheckpoint(
            current_position="Operations specialist",
        ),
    )


def job():
    hard = build_job_hard_facts(
        JobProfile(
            job_id="job-1",
            must_have_capabilities=["Investigation"],
        )
    )
    need = InterpretedJobNeed(
        "need-1",
        "Investigation",
        RequirementImportance.CORE,
        InterpretationAuthority.EXPLICIT,
        (hard.fact_refs[0],),
        requirement_status=JobRequirementStatus.REQUIRED,
        substitutability=RequirementSubstitutability.UNKNOWN,
    )
    profile = AIJobProfileSnapshot(
        job_id="job-1",
        profile_version=2,
        job_signature=hard.job_signature,
        created_at="2026-09-26T00:00:00+00:00",
        needs=(need,),
    )
    return profile, hard


def test_authoritative_service_returns_hiring_case_without_legacy_bucket():
    profile, hard = job()
    result = AuthoritativeHiringCaseService(
        FakeInterpreter()
    ).evaluate(
        candidate_profile=candidate(),
        job_profile=profile,
        hard_facts=hard,
    )
    assert result.classification is HiringCaseClassification.BEST_MATCH
    assert result.authority == "deterministic_hiring_case"
    assert result.candidate_profile_version == 3
    assert result.job_profile_version == 2
    assert result.candidate_signature == "candidate-signature"
    assert result.job_signature == hard.job_signature


def test_stale_job_profile_is_rejected_before_interpretation():
    profile, hard = job()
    stale = replace(profile, job_signature="old")
    try:
        AuthoritativeHiringCaseService(
            FakeInterpreter()
        ).evaluate(
            candidate_profile=candidate(),
            job_profile=stale,
            hard_facts=hard,
        )
    except ValueError as error:
        assert "stale" in str(error).lower()
    else:
        raise AssertionError("Stale job profile must not be evaluated.")


def test_must_have_is_required_but_not_automatically_non_substitutable():
    _, hard = job()
    fact = hard.facts[0]
    assert fact.requirement_status is JobRequirementStatus.REQUIRED
    assert fact.substitutability is RequirementSubstitutability.UNKNOWN
    assert fact.hard_blocker is False


def test_only_explicit_blocker_is_non_substitutable_in_hard_fact_projection():
    hard = build_job_hard_facts(
        JobProfile(
            job_id="job-1",
            must_have_capabilities=["Investigation"],
        ),
        explicit_blockers=("Irish work authorization required",),
    )
    blocker = next(item for item in hard.facts if item.hard_blocker)
    assert blocker.requirement_status is JobRequirementStatus.REQUIRED
    assert (
        blocker.substitutability
        is RequirementSubstitutability.NON_SUBSTITUTABLE
    )


def finite_case(kind, value, candidate_changes=None, ai_state=RequirementEvidenceState.GAP):
    from models.profile_interpretation import HardJobFact, JobHardFacts
    profile, _ = job()
    fact = HardJobFact(
        "finite-1", kind, value, "job:source", hard_blocker=True,
        requirement_status=JobRequirementStatus.REQUIRED,
        substitutability=RequirementSubstitutability.NON_SUBSTITUTABLE,
    )
    hard = JobHardFacts("job-1", "finite-signature", (fact,))
    profile = replace(profile, job_signature=hard.job_signature, needs=(replace(
        profile.needs[0], label=value, hard_fact_refs=(fact.fact_id,), hard_blocker=True,
        substitutability=RequirementSubstitutability.NON_SUBSTITUTABLE,
    ),))
    class Interpreter:
        def analyze_hiring_case(self, **kwargs):
            return HiringCaseInterpretation((RequirementLink("need-1", ai_state, ("experience:1",)),))
    return AuthoritativeHiringCaseService(Interpreter()).evaluate(
        candidate_profile=replace(candidate(), **(candidate_changes or {})),
        job_profile=profile, hard_facts=hard,
    )


def test_required_authorization_compatible_candidate_is_not_blocked():
    from models.profile_interpretation import CandidateWorkAuthorization
    result = finite_case("work_authorization", "Ireland", {
        "work_authorizations": (CandidateWorkAuthorization("Ireland", "authorized", ("experience:1",)),),
    })
    assert result.hard_eligibility_blockers == []
    assert result.classification is not HiringCaseClassification.INELIGIBLE
    assert result.requirements[0].evidence_state is RequirementEvidenceState.PROVEN


@pytest.mark.parametrize("explicit_denial", [False, True])
def test_required_authorization_authoritative_absence_blocks_even_if_ai_claims_proven(explicit_denial):
    from models.profile_interpretation import CandidateFactCoverage, CoverageState, CandidateWorkAuthorization
    result = finite_case("work_authorization", "Ireland", {
        "fact_coverage": CandidateFactCoverage(work_authorizations=CoverageState.CONFIRMED_COMPLETE),
        "work_authorizations": (CandidateWorkAuthorization("Ireland", "denied", ("experience:1",)),) if explicit_denial else (),
    }, ai_state=RequirementEvidenceState.PROVEN)
    assert result.hard_eligibility_blockers == ["Ireland"]
    assert result.classification is HiringCaseClassification.INELIGIBLE


@pytest.mark.parametrize("kind,value,dimension", [
    ("work_authorization", "Ireland", "work_authorizations"),
    ("language", "German", "languages"),
    ("licence", "Legal licence", "licences"),
])
@pytest.mark.parametrize("coverage", ["unknown", "partial"])
@pytest.mark.parametrize("ai_state", [RequirementEvidenceState.GAP, RequirementEvidenceState.PROVEN])
def test_unknown_or_partial_finite_facts_do_not_become_absence_or_ai_proof(kind, value, dimension, coverage, ai_state):
    from models.profile_interpretation import CandidateFactCoverage, CoverageState
    result = finite_case(kind, value, {
        "fact_coverage": CandidateFactCoverage(**{dimension: CoverageState(coverage)}),
    }, ai_state=ai_state)
    assert result.hard_eligibility_blockers == []
    assert result.classification is not HiringCaseClassification.INELIGIBLE
    assert result.requirements[0].evidence_state is RequirementEvidenceState.EVIDENCE_MISSING
    assert result.how_to_prove.items[0].needs_evidence is True


@pytest.mark.parametrize("kind,value,dimension", [
    ("language", "German", "languages"), ("licence", "Legal licence", "licences"),
])
def test_complete_finite_absence_is_relationship_blocker(kind, value, dimension):
    from models.profile_interpretation import CandidateFactCoverage, CoverageState
    result = finite_case(kind, value, {
        "fact_coverage": CandidateFactCoverage(**{dimension: CoverageState.CONFIRMED_COMPLETE}),
    })
    assert result.classification is HiringCaseClassification.INELIGIBLE


def test_unrecognized_authorization_status_is_unknown_even_with_complete_coverage():
    from models.profile_interpretation import CandidateFactCoverage, CoverageState, CandidateWorkAuthorization
    result = finite_case("work_authorization", "Ireland", {
        "fact_coverage": CandidateFactCoverage(work_authorizations=CoverageState.CONFIRMED_COMPLETE),
        "work_authorizations": (CandidateWorkAuthorization("Ireland", "pending", ("experience:1",)),),
    })
    assert result.hard_eligibility_blockers == []
    assert result.requirements[0].evidence_state is RequirementEvidenceState.EVIDENCE_MISSING


@pytest.mark.parametrize("status,expected", [
    ("active", RequirementEvidenceState.PROVEN),
    ("expired", RequirementEvidenceState.GAP),
    ("pending", RequirementEvidenceState.EVIDENCE_MISSING),
    ("unknown", RequirementEvidenceState.EVIDENCE_MISSING),
])
def test_licence_status_preserves_uncertainty(status, expected):
    from models.profile_interpretation import CandidateFactCoverage, CoverageState, CandidateLicence, CredentialStatus
    result = finite_case("licence", "Legal licence", {
        "fact_coverage": CandidateFactCoverage(licences=CoverageState.CONFIRMED_COMPLETE),
        "licences": (CandidateLicence("Legal licence", status=CredentialStatus(status), evidence_refs=("experience:1",)),),
    })
    assert result.requirements[0].evidence_state is expected
    assert bool(result.hard_eligibility_blockers) is (expected is RequirementEvidenceState.GAP)


def test_conflicting_authorizations_require_clarification():
    from models.profile_interpretation import CandidateFactCoverage, CoverageState, CandidateWorkAuthorization
    result = finite_case("work_authorization", "Ireland", {
        "fact_coverage": CandidateFactCoverage(work_authorizations=CoverageState.CONFIRMED_COMPLETE),
        "work_authorizations": tuple(CandidateWorkAuthorization("Ireland", status, ("experience:1",))
                                     for status in ("authorized", "denied")),
    })
    assert result.hard_eligibility_blockers == []
    assert result.requirements[0].evidence_state is RequirementEvidenceState.EVIDENCE_MISSING


def test_unstructured_global_blocker_is_not_candidate_incompatibility():
    result = finite_case("eligibility", "Irish work authorization required")
    assert result.hard_eligibility_blockers == []
    assert result.classification is not HiringCaseClassification.INELIGIBLE


def test_scope_and_staleness_are_checked_before_interpreter_call():
    from unittest.mock import Mock
    profile, hard = job()
    interpreter = Mock()
    service = AuthoritativeHiringCaseService(interpreter)
    with pytest.raises(PermissionError):
        service.evaluate(candidate_profile=candidate(), job_profile=replace(profile, job_id="other"), hard_facts=hard)
    with pytest.raises(ValueError, match="stale"):
        service.evaluate(candidate_profile=candidate(), job_profile=replace(profile, job_signature="old"), hard_facts=hard)
    interpreter.analyze_hiring_case.assert_not_called()
