import pytest

from models.application_contract import ApplicationAnalysisSource
from models.candidate import Candidate
from models.career_update import CareerUpdate
from models.professional_experience_profile import ProfessionalExperienceProfile
from services.application_contract_builder import build_application_contract
from services.application_contract_service import ApplicationContractService


def _candidate(candidate_id="candidate-a"):
    return Candidate(
        id=candidate_id,
        name="Candidate",
        current_role="Operations Specialist",
        current_level="Specialist",
        professional_summary="Operations professional",
        skills=["SQL"],
        proven_capabilities=["Process improvement"],
        transferable_capabilities=["Stakeholder communication"],
        developing_capabilities=["Cloud fundamentals"],
        technical_tools=["Excel"],
        domain_experience=["Customer operations"],
        professional_experiences=[
            ProfessionalExperienceProfile(
                source_experience_id="experience-123",
                company="Example Ltd",
                stated_role="Operations Specialist",
                summary="Improved operational workflows",
                responsibilities=["Managed support escalations"],
                demonstrated_capabilities=["Root cause analysis"],
                tools=["Zendesk"],
                evidence=["Reduced unresolved backlog"],
            )
        ],
    )


def _updates(candidate_id="candidate-a"):
    return [
        CareerUpdate(
            id="update-1",
            candidate_id=candidate_id,
            update_type="course_completed",
            description="Completed an introductory cloud course",
        )
    ]


def _source(
    recommendation="best_match",
    *,
    candidate_id="candidate-a",
    job_id="job-1",
    analysis_id="analysis-1",
    title="Product Operations Specialist",
    analysis=None,
):
    return ApplicationAnalysisSource(
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_id=analysis_id,
        recommendation=recommendation,
        job={
            "id": job_id,
            "title": title,
            "company": "Target Ltd",
            "description": "Improve product operations with SQL",
        },
        analysis=analysis
        if analysis is not None
        else {
            "recommendation": recommendation,
            "development_gaps": ["Advanced SQL"],
            "structural_gaps": ["Direct product ownership"],
            "current_fit": 75,
        },
    )


def _build(source=None, candidate=None, updates=None):
    return build_application_contract(
        candidate=candidate or _candidate(),
        career_updates=_updates() if updates is None else updates,
        analysis_source=source or _source(),
    )


@pytest.mark.parametrize(
    "recommendation",
    ["best_match", "potential", "good_opportunity"],
)
def test_approved_recommendations_are_eligible(recommendation):
    contract = _build(source=_source(recommendation))

    assert contract.recommendation == recommendation
    assert contract.eligible is True


def test_reject_is_not_eligible():
    assert _build(source=_source("reject")).eligible is False


def test_candidate_evidence_and_stable_experience_provenance_are_preserved():
    contract = _build()
    experience = [
        item
        for item in contract.evidence_refs
        if item.source_type == "professional_experience"
    ]

    assert experience
    assert {item.source_id for item in experience} == {"experience-123"}
    assert {item.authority for item in experience} == {"professional_fact"}
    assert any(item.statement == "Managed support escalations" for item in experience)


def test_developing_capability_is_not_promoted_to_professional_fact():
    item = next(
        item
        for item in _build().evidence_refs
        if item.source_type == "developing_capability"
    )

    assert item.statement == "Cloud fundamentals"
    assert item.authority == "developing_evidence"


def test_transferable_capability_has_distinct_authority():
    item = next(
        item
        for item in _build().evidence_refs
        if item.source_type == "transferable_capability"
    )

    assert item.authority == "transferable_evidence"


def test_career_update_preserves_id_and_authority():
    item = next(
        item for item in _build().evidence_refs if item.source_type == "career_update"
    )

    assert item.source_id == "update-1"
    assert item.authority == "candidate_update"
    assert item.metadata == {"update_type": "course_completed"}


def test_development_and_structural_gaps_remain_separate():
    contract = _build()

    assert contract.development_gaps == ["Advanced SQL"]
    assert contract.structural_gaps == ["Direct product ownership"]
    assert all(
        item.statement != "Direct product ownership"
        for item in contract.evidence_refs
    )


def test_candidate_and_job_ownership_mismatches_are_rejected():
    with pytest.raises(PermissionError, match="another candidate"):
        _build(source=_source(candidate_id="candidate-b"))

    mismatched_job = _source()
    mismatched_job = ApplicationAnalysisSource(
        candidate_id=mismatched_job.candidate_id,
        job_id="job-2",
        analysis_id=mismatched_job.analysis_id,
        recommendation=mismatched_job.recommendation,
        job=mismatched_job.job,
        analysis=mismatched_job.analysis,
    )
    with pytest.raises(PermissionError, match="own this job"):
        _build(source=mismatched_job)


def test_source_signature_is_stable_under_ordering_and_formatting_noise():
    candidate_a = _candidate()
    candidate_b = _candidate()
    candidate_b.skills = [" SQL "]
    candidate_b.proven_capabilities = list(reversed(candidate_a.proven_capabilities))
    first_analysis = {
        "recommendation": "best_match",
        "development_gaps": ["SQL", "Reporting"],
        "structural_gaps": ["Direct ownership"],
    }
    second_analysis = {
        "structural_gaps": [" Direct ownership "],
        "development_gaps": ["Reporting", "SQL"],
        "recommendation": "best_match",
    }

    first = _build(candidate=candidate_a, source=_source(analysis=first_analysis))
    second = _build(candidate=candidate_b, source=_source(analysis=second_analysis))

    assert first.source_signature == second.source_signature


@pytest.mark.parametrize(
    "changed_source",
    [
        _source(title="Different job"),
        _source(analysis_id="analysis-2"),
        _source(analysis={"recommendation": "best_match", "current_fit": 90}),
    ],
)
def test_signature_changes_when_job_or_analysis_changes(changed_source):
    assert _build().source_signature != _build(source=changed_source).source_signature


def test_signature_changes_when_candidate_evidence_changes():
    changed = _candidate()
    changed.proven_capabilities.append("Automation design")

    assert _build().source_signature != _build(candidate=changed).source_signature


def test_empty_or_limited_evidence_is_safe():
    candidate = _candidate()
    candidate.professional_experiences = []
    candidate.skills = []
    candidate.proven_capabilities = []
    candidate.transferable_capabilities = []
    candidate.developing_capabilities = []
    candidate.technical_tools = []
    candidate.domain_experience = []

    contract = _build(candidate=candidate, updates=[])

    assert contract.evidence_refs == []
    assert contract.eligible is True


class FakeCandidateRepository:
    def __init__(self, candidate):
        self.candidate = candidate

    def get(self, candidate_id):
        return self.candidate


class FakeUpdateRepository:
    def __init__(self, updates):
        self.updates = updates

    def list_for_candidate(self, candidate_id):
        return self.updates


class FakeSourceRepository:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def get_analysis_source(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.source


def _service(candidate=None, updates=None, source=None):
    source_repository = FakeSourceRepository(source or _source())
    return (
        ApplicationContractService(
            candidate_repository=FakeCandidateRepository(candidate or _candidate()),
            career_update_repository=FakeUpdateRepository(
                _updates() if updates is None else updates
            ),
            source_repository=source_repository,
        ),
        source_repository,
    )


def test_service_scopes_analysis_lookup_to_candidate_and_job():
    service, repository = _service()

    contract = service.build("candidate-a", "job-1")

    assert contract.candidate_id == "candidate-a"
    assert repository.calls == [("candidate-a", "job-1")]


def test_service_rejects_candidate_repository_leak():
    service, _ = _service(candidate=_candidate("candidate-b"))

    with pytest.raises(PermissionError, match="another candidate"):
        service.build("candidate-a", "job-1")


def test_service_rejects_cross_candidate_update():
    service, _ = _service(updates=_updates("candidate-b"))

    with pytest.raises(PermissionError, match="Career update"):
        service.build("candidate-a", "job-1")

