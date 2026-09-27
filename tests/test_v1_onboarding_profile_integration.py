from dataclasses import replace
import pytest

from models.profile_interpretation import CandidateFactCoverage, CoverageState
from services.candidate_profile_source import load_confirmed_candidate_profile_input
from services.profile_interpretation_service import ProfileInterpretationService
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from tests.test_workpilot_v1_onboarding_persistence import repo, begin, response
from tests.test_profile_interpretation_architecture import FakeInterpreter


def finalize(repository):
    begin(repository)
    for i in range(1, 5):
        repository.save_company_answer(candidate_id="a", experience_id="draft",
                                      answer=response(i, "skip" if i == 4 else "text"))
    repository.finalize_company_interview(candidate_id="a", experience_id="draft")


def test_confirmed_answers_reload_into_official_profile_without_generated_candidate(repo):
    finalize(repo)
    repository = ProfileSnapshotRepository()
    interpreter = FakeInterpreter()
    service = ProfileInterpretationService(repository, interpreter)
    first = service.candidate_profile_from_onboarding(candidate_id="a",
        onboarding_repository=CandidateOnboardingRepository())
    assert len(first.source_refs) == 3
    assert all(ref.startswith("professional_experience:draft:") for ref in first.source_refs)
    assert first.evidence_summaries == ("Source answer 3",)
    assert first.fact_coverage.work_authorizations is CoverageState.UNKNOWN
    assert repository.current_candidate("a") == first
    assert service.candidate_profile_from_onboarding(candidate_id="a", onboarding_repository=repo) == first
    assert len(interpreter.candidate_calls) == 1
    assert repository.current_candidate("b") is None


def test_partial_interview_does_not_become_confirmed_profile(repo):
    begin(repo)
    repo.save_company_answer(candidate_id="a", experience_id="draft", answer=response(1))
    service = ProfileInterpretationService(ProfileSnapshotRepository(), FakeInterpreter())
    with pytest.raises(ValueError, match="not available"):
        service.candidate_profile_from_onboarding(candidate_id="a", onboarding_repository=repo)


def test_foreign_repository_result_fails_closed(repo):
    finalize(repo)
    class Forged:
        def list_work_experiences(self, cid):
            return repo.list_work_experiences("a")
    with pytest.raises(PermissionError):
        load_confirmed_candidate_profile_input("b", Forged())


def test_narrative_cannot_certify_authoritative_absence(repo):
    finalize(repo)
    class Forged(FakeInterpreter):
        def build_candidate_profile(self, **kwargs):
            return replace(super().build_candidate_profile(**kwargs), fact_coverage=CandidateFactCoverage(
                work_authorizations=CoverageState.CONFIRMED_COMPLETE))
    snapshots = ProfileSnapshotRepository()
    with pytest.raises(ValueError, match="complete"):
        ProfileInterpretationService(snapshots, Forged()).candidate_profile_from_onboarding(
            candidate_id="a", onboarding_repository=repo)
    assert snapshots.current_candidate("a") is None
