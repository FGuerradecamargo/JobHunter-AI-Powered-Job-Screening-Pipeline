from dataclasses import replace

import pytest

from models.application_context import ApplicationContext
from models.application_contract import (
    ApplicationAnalysisSource,
    ApplicationContract,
    ApplicationEvidenceRef,
)
from models.tailored_cv_contract import (
    CVValidationIssue,
    DraftTailoredCV,
    TailoredCVGenerationResult,
    TailoredCVStatement,
)
from services.application_contract_service import ApplicationAnalysisNotFoundError
from services.prepare_application_service import PrepareApplicationService
from services.tailored_cv_generation_service import TailoredCVGenerationService


def _evidence():
    return ApplicationEvidenceRef(
        evidence_ref="e-direct",
        source_type="proven_capability",
        source_id="candidate:candidate-a:proven_capabilities",
        authority="professional_fact",
        statement="Process improvement",
    )


def _contract(recommendation="best_match"):
    return ApplicationContract(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        recommendation=recommendation,
        eligible=recommendation != "reject",
        evidence_refs=[_evidence()],
        source_signature="contract-signature",
    )


def _source(recommendation="best_match"):
    return ApplicationAnalysisSource(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        recommendation=recommendation,
        job={"id": "job-1", "title": "Operations Specialist"},
        analysis={"recommendation": recommendation},
    )


def _context(recommendation="best_match"):
    evidence = _evidence()
    return ApplicationContext(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        contract_signature="contract-signature",
        direct_evidence=[evidence],
        available_evidence=[evidence],
        source_signature="context-signature",
        recommendation=recommendation,
        eligible=recommendation != "reject",
    )


def _cv():
    return DraftTailoredCV(
        candidate_id="candidate-a",
        job_id="job-1",
        application_context_signature="context-signature",
        headline=TailoredCVStatement(
            text="Operations specialist",
            claim_type="summary",
            evidence_refs=["e-direct"],
        ),
    )


def _valid_output():
    return {
        "candidate_id": "candidate-a",
        "job_id": "job-1",
        "application_context_signature": "context-signature",
        "headline": {
            "text": "Operations specialist",
            "claim_type": "summary",
            "evidence_refs": ["e-direct"],
        },
        "professional_summary": [],
        "key_skills": [],
        "experiences": [],
        "additional_relevant_information": [],
        "schema_version": "tailored-cv-v1",
    }


class FakeContractService:
    def __init__(self, contract=None, source=None, error=None):
        self.contract = contract or _contract()
        self.source = source or _source()
        self.error = error
        self.calls = []

    def build_with_source(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        if self.error:
            raise self.error
        return self.contract, self.source


class FakeContextService:
    def __init__(self, context=None, error=None):
        self.context = context or _context()
        self.error = error
        self.calls = []

    def build_from_contract(self, contract, source):
        self.calls.append((contract, source))
        if self.error:
            raise self.error
        return self.context


class FakeGenerationService:
    def __init__(self, result=None, error=None):
        self.result = result or TailoredCVGenerationResult(
            status="validated",
            cv=_cv(),
        )
        self.error = error
        self.calls = []

    def generate(self, context):
        self.calls.append(context)
        if self.error:
            raise self.error
        return self.result


class FakeGeneratorClient:
    def __init__(self, output):
        self.output = output
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.output


def _service(contract_service=None, context_service=None, generation_service=None):
    return PrepareApplicationService(
        contract_service=contract_service or FakeContractService(),
        context_service=context_service or FakeContextService(),
        generation_service=generation_service or FakeGenerationService(),
    )


@pytest.mark.parametrize(
    "recommendation",
    ["best_match", "potential", "good_opportunity"],
)
def test_explicit_prepare_succeeds_for_eligible_recommendations(recommendation):
    contract_service = FakeContractService(
        _contract(recommendation),
        _source(recommendation),
    )
    context_service = FakeContextService(_context(recommendation))
    generation_service = FakeGenerationService()
    result = _service(
        contract_service,
        context_service,
        generation_service,
    ).prepare("candidate-a", "job-1")

    assert result.status == "prepared"
    assert result.cv == _cv()
    assert contract_service.calls == [("candidate-a", "job-1")]
    assert len(context_service.calls) == 1
    assert generation_service.calls == [_context(recommendation)]


def test_reject_is_ineligible_and_never_calls_context_or_generator():
    contract_service = FakeContractService(_contract("reject"), _source("reject"))
    context_service = FakeContextService()
    generation_service = FakeGenerationService()
    result = _service(
        contract_service,
        context_service,
        generation_service,
    ).prepare("candidate-a", "job-1")

    assert result.status == "ineligible"
    assert result.error_code == "ineligible_application"
    assert context_service.calls == []
    assert generation_service.calls == []


def test_no_analysis_returns_structured_failure_without_generation():
    contract_service = FakeContractService(
        error=ApplicationAnalysisNotFoundError("internal detail")
    )
    generation_service = FakeGenerationService()
    result = _service(
        contract_service=contract_service,
        generation_service=generation_service,
    ).prepare("candidate-a", "job-1")

    assert result.status == "failed"
    assert result.error_code == "analysis_not_found"
    assert "internal detail" not in result.error_message
    assert generation_service.calls == []


@pytest.mark.parametrize(
    ("contract", "source"),
    [
        (replace(_contract(), candidate_id="candidate-b"), _source()),
        (replace(_contract(), job_id="job-2"), _source()),
        (_contract(), replace(_source(), candidate_id="candidate-b")),
        (_contract(), replace(_source(), job_id="job-2")),
        (_contract(), replace(_source(), analysis_id="analysis-2")),
    ],
)
def test_contract_and_analysis_scope_mismatches_are_rejected(contract, source):
    generation_service = FakeGenerationService()
    result = _service(
        contract_service=FakeContractService(contract, source),
        generation_service=generation_service,
    ).prepare("candidate-a", "job-1")

    assert result.error_code == "scope_mismatch"
    assert generation_service.calls == []


def test_repository_scope_error_is_returned_safely():
    result = _service(
        contract_service=FakeContractService(error=PermissionError("private"))
    ).prepare("candidate-a", "job-1")

    assert result.error_code == "scope_mismatch"
    assert "private" not in result.error_message


@pytest.mark.parametrize(
    "context",
    [
        replace(_context(), candidate_id="candidate-b"),
        replace(_context(), job_id="job-2"),
        replace(_context(), analysis_id="analysis-2"),
        replace(_context(), contract_signature="other-contract"),
    ],
)
def test_cross_scope_application_context_is_rejected(context):
    generation_service = FakeGenerationService()
    result = _service(
        context_service=FakeContextService(context),
        generation_service=generation_service,
    ).prepare("candidate-a", "job-1")

    assert result.error_code == "scope_mismatch"
    assert generation_service.calls == []


def test_prepare_invokes_real_generation_pipeline_with_fake_client_once():
    client = FakeGeneratorClient(_valid_output())
    generation_service = TailoredCVGenerationService(client)
    result = _service(generation_service=generation_service).prepare(
        "candidate-a",
        "job-1",
    )

    assert result.status == "prepared"
    assert result.cv.candidate_id == "candidate-a"
    assert result.generation_status == "validated"
    assert len(client.requests) == 1


def test_generation_failure_is_propagated_without_cv():
    generation = TailoredCVGenerationResult(
        status="generation_error",
        error_code="generator_client_error",
        error_message="The generator failed safely.",
    )
    result = _service(
        generation_service=FakeGenerationService(generation)
    ).prepare("candidate-a", "job-1")

    assert result.status == "generation_failed"
    assert result.error_code == "generator_client_error"
    assert result.cv is None


def test_validation_failure_is_propagated_without_invalid_cv():
    issue = CVValidationIssue(
        code="unknown_evidence_ref",
        location="headline",
        message="Unknown evidence.",
    )
    generation = TailoredCVGenerationResult(
        status="validation_failed",
        validation_issues=[issue],
        error_code="repair_exhausted",
    )
    result = _service(
        generation_service=FakeGenerationService(generation)
    ).prepare("candidate-a", "job-1")

    assert result.status == "generation_failed"
    assert result.validation_issues == [issue]
    assert result.cv is None


def test_validated_after_repair_returns_prepared_cv():
    generation = TailoredCVGenerationResult(
        status="validated_after_repair",
        cv=_cv(),
    )
    result = _service(
        generation_service=FakeGenerationService(generation)
    ).prepare("candidate-a", "job-1")

    assert result.status == "prepared"
    assert result.generation_status == "validated_after_repair"
    assert result.cv == _cv()


def test_viewing_or_analyzing_does_not_implicitly_prepare_or_generate():
    contract_service = FakeContractService()
    context_service = FakeContextService()
    generation_service = FakeGenerationService()
    service = _service(contract_service, context_service, generation_service)

    viewed_job = {"candidate_id": "candidate-a", "job_id": "job-1"}
    analyzed_job = _source()

    assert viewed_job["job_id"] == analyzed_job.job_id
    assert contract_service.calls == []
    assert context_service.calls == []
    assert generation_service.calls == []

    service.prepare("candidate-a", "job-1")
    assert len(generation_service.calls) == 1


def test_prepare_does_not_write_or_mark_job_as_applied():
    contract_service = FakeContractService()
    result = _service(contract_service=contract_service).prepare(
        "candidate-a",
        "job-1",
    )

    assert result.status == "prepared"
    assert not hasattr(contract_service, "writes")
    assert not hasattr(result, "applied_at")
    assert not hasattr(result, "opportunity_state")


def test_invalid_request_does_not_enter_pipeline():
    contract_service = FakeContractService()
    result = _service(contract_service=contract_service).prepare(" ", "job-1")

    assert result.error_code == "invalid_request"
    assert contract_service.calls == []
