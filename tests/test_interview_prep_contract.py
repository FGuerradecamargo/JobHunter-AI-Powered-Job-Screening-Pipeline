from dataclasses import replace
from pathlib import Path

import pytest

from models.application_context import ApplicationContext, PositioningTheme
from models.application_contract import ApplicationEvidenceRef
from models.application_outcome import ApplicationOutcome
from models.prepare_application import PrepareApplicationResult
from models.tailored_cv_contract import DraftTailoredCV, TailoredCVStatement
from services.interview_prep_contract_builder import build_interview_prep_contract
from services.interview_prep_contract_service import (
    InterviewPrepContractService,
    InterviewPrepSourceNotFoundError,
)


def _evidence(
    evidence_ref="e-professional",
    authority="professional_fact",
    statement="Improved customer operations",
):
    return ApplicationEvidenceRef(
        evidence_ref=evidence_ref,
        source_type=(
            "professional_experience"
            if authority == "professional_fact"
            else "career_update"
        ),
        source_id="experience-1" if authority == "professional_fact" else "update-1",
        authority=authority,
        statement=statement,
    )


def _context(**changes):
    professional = _evidence()
    developing = _evidence(
        "e-developing", "developing_evidence", "Learning Kubernetes"
    )
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        contract_signature="contract-signature",
        job_title="Product Operations Specialist",
        company="Example Ltd",
        role_family="Product Operations",
        job_level="Specialist",
        core_requirements=["Process improvement", "Stakeholder management"],
        direct_evidence=[professional],
        developing_evidence=[developing],
        available_evidence=[professional, developing],
        development_gaps=["Advanced SQL"],
        structural_gaps=["No production Kubernetes experience"],
        positioning_themes=[
            PositioningTheme(
                theme="Customer operations",
                evidence_refs=["e-professional"],
            )
        ],
        source_signature="application-context-signature",
        recommendation="best_match",
        eligible=True,
    )
    values.update(changes)
    return ApplicationContext(**values)


class ContextService:
    def __init__(self, context=None):
        self.context = context or _context()
        self.calls = []

    def build(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.context


class OutcomeRepository:
    def __init__(self, *, status="applied", outcome=None, application=None):
        self.application = application or {
            "candidate_id": "candidate-a",
            "job_id": "job-1",
            "status": status,
            "opportunity_state": status,
            "applied_at": "2026-09-12",
        }
        self.outcome = outcome
        self.calls = []

    def get_application(self, candidate_id, job_id):
        self.calls.append(("application", candidate_id, job_id))
        return self.application

    def get(self, candidate_id, job_id):
        self.calls.append(("outcome", candidate_id, job_id))
        return self.outcome


def _service(*, repository=None, context_service=None):
    return InterviewPrepContractService(
        outcome_repository=repository or OutcomeRepository(),
        context_service=context_service or ContextService(),
    )


@pytest.mark.parametrize("stage", ["interview", "final_interview"])
def test_active_interview_stages_are_eligible(stage):
    outcome = ApplicationOutcome(
        candidate_id="candidate-a", job_id="job-1", interview_stage=stage
    )

    contract = _service(
        repository=OutcomeRepository(outcome=outcome)
    ).build("candidate-a", "job-1")

    assert contract.eligible is True
    assert contract.interview_stage == stage
    assert contract.application_final_status == ""


@pytest.mark.parametrize(
    ("status", "stage", "final_status"),
    [
        ("applied", "", ""),
        ("rejected_before_interview", "", "rejected"),
        ("rejected_after_interview", "interview", "rejected"),
        ("applied", "interview", "withdrawn"),
        ("offer", "final_interview", "offer"),
        ("offer", "final_interview", "accepted"),
        ("offer", "final_interview", "declined"),
    ],
)
def test_non_active_states_are_not_eligible(status, stage, final_status):
    outcome = (
        ApplicationOutcome(
            candidate_id="candidate-a",
            job_id="job-1",
            interview_stage=stage,
            final_status=final_status,
        )
        if stage or final_status
        else None
    )

    contract = _service(
        repository=OutcomeRepository(status=status, outcome=outcome)
    ).build("candidate-a", "job-1")

    assert contract.eligible is False
    assert contract.application_final_status == final_status


def test_legacy_in_process_lifecycle_remains_eligible_without_outcome():
    contract = _service(
        repository=OutcomeRepository(status="in_process")
    ).build("candidate-a", "job-1")

    assert contract.eligible is True
    assert contract.interview_stage == "interview"


def test_missing_candidate_job_relationship_fails_closed():
    repository = OutcomeRepository()
    repository.application = None

    with pytest.raises(InterviewPrepSourceNotFoundError):
        _service(repository=repository).build("candidate-a", "missing")


@pytest.mark.parametrize(
    "application",
    [
        {"candidate_id": "candidate-b", "job_id": "job-1", "status": "in_process"},
        {"candidate_id": "candidate-a", "job_id": "job-2", "status": "in_process"},
    ],
)
def test_candidate_and_job_relationship_mismatch_is_rejected(application):
    with pytest.raises(PermissionError, match="another scope"):
        _service(
            repository=OutcomeRepository(application=application)
        ).build("candidate-a", "job-1")


def test_outcome_from_another_candidate_is_rejected():
    outcome = ApplicationOutcome(
        candidate_id="candidate-b", job_id="job-1", interview_stage="interview"
    )

    with pytest.raises(PermissionError, match="another scope"):
        _service(
            repository=OutcomeRepository(outcome=outcome)
        ).build("candidate-a", "job-1")


def test_application_context_from_another_job_is_rejected():
    with pytest.raises(PermissionError, match="another scope"):
        _service(
            repository=OutcomeRepository(status="in_process"),
            context_service=ContextService(_context(job_id="job-2")),
        ).build("candidate-a", "job-1")


def test_authorized_evidence_provenance_and_authority_are_preserved():
    contract = _service(
        repository=OutcomeRepository(status="in_process")
    ).build("candidate-a", "job-1")

    by_ref = {item.evidence_ref: item for item in contract.authorized_evidence}
    assert by_ref["e-professional"].source_id == "experience-1"
    assert by_ref["e-professional"].authority == "professional_fact"
    assert by_ref["e-developing"].authority == "developing_evidence"
    assert by_ref["e-developing"].statement == "Learning Kubernetes"


def test_requirements_themes_and_gaps_are_carried_without_reclassification():
    context = _context()

    contract = build_interview_prep_contract(
        context=context,
        interview_stage="interview",
        eligible=True,
    )

    assert contract.target_requirements == context.core_requirements
    assert contract.development_gaps == context.development_gaps
    assert contract.protected_structural_gaps == context.structural_gaps
    assert contract.positioning_themes == context.positioning_themes


def test_prepared_cv_cannot_expand_authorized_evidence_boundary():
    invented_cv = DraftTailoredCV(
        candidate_id="candidate-a",
        job_id="job-1",
        application_context_signature="application-context-signature",
        headline=TailoredCVStatement(
            text="Invented platform owner",
            claim_type="summary",
            evidence_refs=["invented-ref"],
        ),
    )
    prepared = PrepareApplicationResult(
        status="prepared",
        candidate_id="candidate-a",
        job_id="job-1",
        application_context_signature="application-context-signature",
        cv=invented_cv,
        generation_status="validated",
    )

    contract = _service(
        repository=OutcomeRepository(status="in_process")
    ).build("candidate-a", "job-1")

    assert prepared.cv.headline.evidence_refs == ["invented-ref"]
    assert {item.evidence_ref for item in contract.authorized_evidence} == {
        "e-professional", "e-developing"
    }


def test_absence_of_prepared_cv_does_not_block_contract():
    contract = _service(
        repository=OutcomeRepository(status="in_process")
    ).build("candidate-a", "job-1")

    assert contract.eligible
    assert len(contract.authorized_evidence) == 2


def test_signature_is_deterministic_under_ordering_and_whitespace_noise():
    context = _context()
    noisy_evidence = [
        replace(item, statement=f"  {item.statement}  ")
        for item in reversed(context.available_evidence)
    ]
    noisy = replace(
        context,
        available_evidence=noisy_evidence,
        core_requirements=list(reversed(context.core_requirements)),
        structural_gaps=["  No production Kubernetes experience  "],
    )

    first = build_interview_prep_contract(
        context=context, interview_stage="interview", eligible=True
    )
    second = build_interview_prep_contract(
        context=noisy, interview_stage="  INTERVIEW  ", eligible=True
    )

    assert first.source_signature == second.source_signature


def test_relevant_evidence_and_stage_change_signature():
    context = _context()
    base = build_interview_prep_contract(
        context=context, interview_stage="interview", eligible=True
    )
    changed_evidence = replace(
        context,
        available_evidence=[
            replace(context.available_evidence[0], statement="Different fact"),
            context.available_evidence[1],
        ],
    )

    evidence_contract = build_interview_prep_contract(
        context=changed_evidence, interview_stage="interview", eligible=True
    )
    stage_contract = build_interview_prep_contract(
        context=context, interview_stage="final_interview", eligible=True
    )

    assert base.source_signature != evidence_contract.source_signature
    assert base.source_signature != stage_contract.source_signature


def test_legacy_interview_prep_is_not_an_authority_or_signature_input():
    builder_source = Path("services/interview_prep_contract_builder.py").read_text(
        encoding="utf-8"
    )

    assert "legacy" not in builder_source
    assert "likely_interview_topics" not in builder_source
    assert 'analysis.get("interview_prep")' not in builder_source


def test_contract_boundary_has_no_generator_llm_or_api_path():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "models/interview_prep_contract.py",
            "services/interview_prep_contract_builder.py",
            "services/interview_prep_contract_service.py",
        )
    ).lower()

    assert "openai" not in source
    assert "llm" not in source
    assert ".generate(" not in source
    assert "requests." not in source
