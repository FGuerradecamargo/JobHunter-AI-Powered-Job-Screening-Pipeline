import pytest

from models.application_contract import (
    ApplicationAnalysisSource,
    ApplicationContract,
    ApplicationEvidenceRef,
)
from models.candidate import Candidate
from models.career_update import CareerUpdate
from services.application_context_builder import build_application_context
from services.application_context_service import ApplicationContextService


def _evidence(
    evidence_ref,
    statement,
    authority,
    source_type,
    source_id="source-1",
):
    return ApplicationEvidenceRef(
        evidence_ref=evidence_ref,
        source_type=source_type,
        source_id=source_id,
        authority=authority,
        statement=statement,
    )


def _contract(recommendation="best_match", *, candidate_id="candidate-a"):
    return ApplicationContract(
        candidate_id=candidate_id,
        job_id="job-1",
        analysis_id="analysis-1",
        recommendation=recommendation,
        eligible=recommendation != "reject",
        evidence_refs=[
            _evidence(
                "e-direct",
                "Process improvement",
                "professional_fact",
                "proven_capability",
            ),
            _evidence(
                "e-experience",
                "Managed support escalations",
                "professional_fact",
                "professional_experience",
                "experience-123",
            ),
            _evidence(
                "e-transferable",
                "Stakeholder communication",
                "transferable_evidence",
                "transferable_capability",
            ),
            _evidence(
                "e-supporting",
                "SQL",
                "candidate_profile_fact",
                "skill",
            ),
            _evidence(
                "e-developing",
                "Cloud fundamentals",
                "developing_evidence",
                "developing_capability",
            ),
            _evidence(
                "e-irrelevant",
                "Unrelated legacy tool",
                "candidate_profile_fact",
                "technical_tool",
            ),
        ],
        development_gaps=["Advanced reporting"],
        structural_gaps=["Direct product ownership"],
        source_signature="contract-signature",
    )


def _source(
    recommendation="best_match",
    *,
    candidate_id="candidate-a",
    job_id="job-1",
    analysis_id="analysis-1",
    job=None,
    analysis=None,
):
    return ApplicationAnalysisSource(
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_id=analysis_id,
        recommendation=recommendation,
        job=job
        or {
            "id": job_id,
            "title": "Product Operations Specialist",
            "company": "Target Ltd",
            "description": "SQL and cloud experience required",
        },
        analysis=analysis
        or {
            "recommendation": recommendation,
            "job_level": "Intermediate",
            "core_requirements": ["SQL", "Process improvement"],
            "requirements_met": ["Process improvement", "SQL"],
            "strengths": [
                "Stakeholder communication",
                "Managed support escalations",
            ],
            "market_signal": {
                "role_family": "Product Ops",
                "market_strengths": ["Stakeholder communication"],
            },
        },
    )


def _build(contract=None, source=None):
    return build_application_context(
        contract=contract or _contract(),
        analysis_source=source or _source(),
    )


@pytest.mark.parametrize(
    "recommendation",
    ["best_match", "potential", "good_opportunity"],
)
def test_eligible_recommendations_build_context(recommendation):
    context = _build(
        contract=_contract(recommendation),
        source=_source(recommendation),
    )

    assert context.candidate_id == "candidate-a"
    assert context.job_id == "job-1"
    assert context.contract_signature == "contract-signature"


def test_ineligible_contract_is_refused():
    with pytest.raises(ValueError, match="not eligible"):
        _build(contract=_contract("reject"), source=_source("reject"))


def test_authorized_evidence_is_grouped_without_authority_promotion():
    context = _build()

    assert {item.evidence_ref for item in context.direct_evidence} == {
        "e-direct",
        "e-experience",
    }
    assert [item.evidence_ref for item in context.transferable_evidence] == [
        "e-transferable"
    ]
    assert [item.evidence_ref for item in context.supporting_evidence] == [
        "e-supporting"
    ]
    assert context.developing_evidence == []


def test_developing_evidence_never_becomes_direct():
    source = _source()
    source.analysis["requirements_met"].append("Cloud fundamentals")
    context = _build(source=source)

    assert [item.evidence_ref for item in context.developing_evidence] == [
        "e-developing"
    ]
    assert "e-developing" not in {
        item.evidence_ref for item in context.direct_evidence
    }


def test_irrelevant_evidence_is_available_but_not_selected():
    context = _build()

    assert "e-irrelevant" in {
        item.evidence_ref for item in context.available_evidence
    }
    selected = {
        item.evidence_ref
        for group in (
            context.direct_evidence,
            context.transferable_evidence,
            context.supporting_evidence,
            context.developing_evidence,
        )
        for item in group
    }
    assert "e-irrelevant" not in selected


def test_stable_experience_provenance_is_preserved():
    experience = next(
        item for item in _build().direct_evidence if item.evidence_ref == "e-experience"
    )

    assert experience.source_id == "experience-123"
    assert experience.source_type == "professional_experience"


def test_protected_gaps_are_preserved_unchanged():
    context = _build()

    assert context.development_gaps == ["Advanced reporting"]
    assert context.structural_gaps == ["Direct product ownership"]


def test_positioning_theme_requires_actual_authorized_support():
    themes = _build().positioning_themes

    assert {item.theme for item in themes} == {
        "Managed support escalations",
        "Process improvement",
        "SQL",
        "Stakeholder communication",
    }
    assert all(item.evidence_refs for item in themes)


def test_job_keyword_alone_cannot_manufacture_theme():
    source = _source(
        job={
            "id": "job-1",
            "title": "Cloud Engineer",
            "company": "Target Ltd",
            "description": "Kubernetes ownership",
        },
        analysis={
            "recommendation": "best_match",
            "core_requirements": ["Kubernetes ownership"],
            "requirements_met": [],
            "strengths": [],
            "market_signal": {},
        },
    )

    assert _build(source=source).positioning_themes == []


def test_job_and_analysis_fields_are_preserved_without_prose_generation():
    context = _build()

    assert context.job_title == "Product Operations Specialist"
    assert context.company == "Target Ltd"
    assert context.role_family == "Product Operations"
    assert context.job_level == "Intermediate"
    assert context.core_requirements == ["Process improvement", "SQL"]


def test_signature_is_stable_under_ordering_and_whitespace_noise():
    first = _source()
    second = _source(
        analysis={
            "market_signal": {
                "market_strengths": [" Stakeholder communication "],
                "role_family": "Product Ops",
            },
            "strengths": [
                "Managed support escalations",
                "Stakeholder communication",
            ],
            "requirements_met": [" SQL ", "Process improvement"],
            "core_requirements": ["Process improvement", "SQL"],
            "job_level": "Intermediate",
            "recommendation": "best_match",
        }
    )

    assert _build(source=first).source_signature == _build(source=second).source_signature


@pytest.mark.parametrize(
    ("contract", "source"),
    [
        (
            ApplicationContract(
                **{
                    **_contract().__dict__,
                    "source_signature": "changed-contract",
                }
            ),
            _source(),
        ),
        (_contract(), _source(job={"id": "job-1", "title": "Changed job"})),
        (
            _contract(),
            _source(
                analysis={
                    "recommendation": "best_match",
                    "core_requirements": ["Changed requirement"],
                }
            ),
        ),
    ],
)
def test_signature_changes_with_contract_job_or_analysis(contract, source):
    assert _build().source_signature != _build(
        contract=contract,
        source=source,
    ).source_signature


@pytest.mark.parametrize(
    ("contract", "source", "message"),
    [
        (_contract(candidate_id="candidate-b"), _source(), "another candidate"),
        (_contract(), _source(job_id="job-2"), "another job"),
        (_contract(), _source(analysis_id="analysis-2"), "another analysis"),
    ],
)
def test_candidate_job_and_analysis_mismatches_are_rejected(
    contract,
    source,
    message,
):
    with pytest.raises(PermissionError, match=message):
        _build(contract=contract, source=source)


def test_empty_evidence_is_safe():
    contract = ApplicationContract(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        recommendation="best_match",
        eligible=True,
        source_signature="empty-contract",
    )
    context = _build(contract=contract)

    assert context.direct_evidence == []
    assert context.transferable_evidence == []
    assert context.positioning_themes == []


class FakeCandidateRepository:
    def __init__(self, candidate):
        self.candidate = candidate

    def get(self, candidate_id):
        return self.candidate


class FakeUpdateRepository:
    def list_for_candidate(self, candidate_id):
        return []


class FakeSourceRepository:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def get_analysis_source(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.source


def test_service_uses_candidate_scoped_source_once():
    source_repository = FakeSourceRepository(_source())
    service = ApplicationContextService(
        candidate_repository=FakeCandidateRepository(
            Candidate(
                id="candidate-a",
                name="Candidate",
                current_role="Role",
                current_level="Level",
                professional_summary="Summary",
            )
        ),
        career_update_repository=FakeUpdateRepository(),
        source_repository=source_repository,
    )

    context = service.build("candidate-a", "job-1")

    assert context.candidate_id == "candidate-a"
    assert source_repository.calls == [("candidate-a", "job-1")]

