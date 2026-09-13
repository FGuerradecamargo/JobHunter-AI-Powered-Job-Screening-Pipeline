from dataclasses import replace
from pathlib import Path

import pytest

from models.application_context import ApplicationContext
from models.application_contract import (
    ApplicationAnalysisSource,
    ApplicationContract,
    ApplicationEvidenceRef,
)
from models.application_outcome import ApplicationOutcome
from models.prepare_application import PrepareApplicationResult
from models.tailored_cv_contract import (
    DraftTailoredCV,
    TailoredCVGenerationResult,
    TailoredCVStatement,
)
from services.application_outcome_ui import load_application_outcome_view
from services.career_evidence_builder import build_outcome_evidence
from services.prepare_application_service import PrepareApplicationService
from services.prepared_application_ui import (
    build_prepared_cv_view,
    get_prepared_application,
    handle_prepare_application_action,
    prepared_application_state_key,
)
from services.prepared_cv_exporter import export_cached_prepared_cv_docx
from services.tailored_cv_generation_service import TailoredCVGenerationService


def _statement():
    return TailoredCVStatement(
        text="Evidence-led operator",
        claim_type="summary",
        evidence_refs=["e-1"],
    )


def _cv(candidate_id="candidate-a", job_id="job-1", signature="context-1"):
    return DraftTailoredCV(
        candidate_id=candidate_id,
        job_id=job_id,
        application_context_signature=signature,
        headline=_statement(),
    )


def _prepared(cv=None, generation_status="validated"):
    return PrepareApplicationResult(
        status="prepared",
        candidate_id="candidate-a",
        job_id="job-1",
        application_context_signature="context-1",
        cv=cv or _cv(),
        generation_status=generation_status,
    )


@pytest.mark.parametrize(
    "forged",
    [
        _prepared(_cv(candidate_id="candidate-b")),
        _prepared(_cv(job_id="job-2")),
        _prepared(_cv(signature="forged-signature")),
        _prepared(generation_status="validation_failed"),
    ],
)
def test_forged_cached_prepared_result_is_unreadable_and_unexportable(forged):
    state = {prepared_application_state_key("candidate-a", "job-1"): forged}

    assert get_prepared_application(
        state, candidate_id="candidate-a", job_id="job-1"
    ) is None
    assert build_prepared_cv_view(forged) is None
    with pytest.raises(ValueError, match="not found"):
        export_cached_prepared_cv_docx(
            state,
            candidate_id="candidate-a",
            job_id="job-1",
            candidate_name="Candidate",
            company="Company",
            role="Role",
        )


class ForgedPreparationService:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def prepare(self, candidate_id, job_id):
        self.calls += 1
        return self.result


def test_forged_preparation_result_is_not_cached_as_prepared():
    state = {}
    service = ForgedPreparationService(_prepared(_cv(candidate_id="candidate-b")))

    result = handle_prepare_application_action(
        state,
        candidate_id="candidate-a",
        job_id="job-1",
        analysis={"recommendation": "best_match"},
        action_requested=True,
        preparation_service=service,
    )

    assert result.status == "failed"
    assert result.error_code == "invalid_preparation_result"
    assert state == {}


def _evidence():
    return ApplicationEvidenceRef(
        evidence_ref="e-1",
        source_type="proven_capability",
        source_id="candidate-a:capability",
        authority="professional_fact",
        statement="Evidence-led operations",
    )


class ContractService:
    def build_with_source(self, candidate_id, job_id):
        return (
            ApplicationContract(
                candidate_id="candidate-a",
                job_id="job-1",
                analysis_id="analysis-1",
                recommendation="best_match",
                eligible=True,
                evidence_refs=[_evidence()],
                source_signature="contract-1",
            ),
            ApplicationAnalysisSource(
                candidate_id="candidate-a",
                job_id="job-1",
                analysis_id="analysis-1",
                recommendation="best_match",
                job={"id": "job-1"},
                analysis={"recommendation": "best_match"},
            ),
        )


class ContextService:
    def build_from_contract(self, contract, source):
        evidence = _evidence()
        return ApplicationContext(
            candidate_id="candidate-a",
            job_id="job-1",
            analysis_id="analysis-1",
            contract_signature="contract-1",
            direct_evidence=[evidence],
            available_evidence=[evidence],
            source_signature="context-1",
            recommendation="best_match",
            eligible=True,
        )


class ValidatedButForgedGenerator:
    def generate(self, context):
        return TailoredCVGenerationResult(
            status="validated",
            cv=_cv(candidate_id="candidate-b"),
        )


def test_prepare_service_rejects_forged_validated_generator_identity():
    service = PrepareApplicationService(
        contract_service=ContractService(),
        context_service=ContextService(),
        generation_service=ValidatedButForgedGenerator(),
    )

    result = service.prepare("candidate-a", "job-1")

    assert result.status == "generation_failed"
    assert result.error_code == "validated_cv_scope_mismatch"
    assert result.cv is None


def test_invalid_generator_object_fails_closed_without_transport():
    context = ContextService().build_from_contract(None, None)

    result = TailoredCVGenerationService(object()).generate(context)

    assert result.status == "generation_error"
    assert result.error_code == "generator_client_error"
    assert result.cv is None


@pytest.mark.parametrize("limit", [-1, 2, 99])
def test_repair_limit_can_never_exceed_one(limit):
    with pytest.raises(ValueError, match="zero or one"):
        TailoredCVGenerationService(object(), max_repair_attempts=limit)


def test_duplicate_outcome_rows_create_one_evidence_record():
    outcome = {
        "job_id": "job-1",
        "final_status": "rejected",
        "interview_stage": "interview",
        "outcome_date": "2026-09-13",
    }

    records = build_outcome_evidence([outcome, dict(outcome), dict(outcome)])

    assert len(records) == 1
    assert records[0].statement == "rejected"
    assert records[0].metadata["is_employer_rejection"] is True


class OutcomeRepository:
    def __init__(self, outcome):
        self.outcome = outcome
        self.reads = []

    def get(self, candidate_id, job_id):
        self.reads.append((candidate_id, job_id))
        if (candidate_id, job_id) != ("candidate-a", "job-1"):
            return None
        return self.outcome


@pytest.mark.parametrize(
    ("legacy_status", "expected", "actions"),
    [
        ("in_process", "Interview", ["final_interview", "rejected", "withdrawn"]),
        ("rejected_before_interview", "Rejected", []),
        ("rejected_after_interview", "Rejected", []),
        ("offer", "Offer", ["accepted", "declined", "withdrawn"]),
    ],
)
def test_legacy_lifecycle_status_maps_without_writing(
    legacy_status, expected, actions
):
    repository = OutcomeRepository(None)

    view = load_application_outcome_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status=legacy_status,
        repository=repository,
    )

    assert view.status_label == expected
    assert [item.value for item in view.actions] == actions
    assert repository.reads == [("candidate-a", "job-1")]


def test_persisted_terminal_outcome_overrides_stale_lifecycle_status():
    repository = OutcomeRepository(
        ApplicationOutcome(
            candidate_id="candidate-a",
            job_id="job-1",
            final_status="accepted",
        )
    )

    view = load_application_outcome_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        repository=repository,
    )

    assert view.status_label == "Accepted"
    assert view.actions == ()


def test_current_sprint_11_ui_has_no_direct_persistence_bypass():
    sources = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in ("app.py", "pages/1_Opportunities.py")
    )

    assert "save_candidate_application_outcome(" not in sources
    assert "update_candidate_job_status(" not in sources
    assert "ApplicationOutcomeService" in sources
    assert "ApplicationLifecycleService" in sources


def test_ai_transport_boundary_remains_single_and_constructor_is_inert():
    adapter = Path("services/ai/tailored_cv_generator_adapter.py").read_text(
        encoding="utf-8"
    )
    factory = Path("services/prepare_application_factory.py").read_text(
        encoding="utf-8"
    )

    assert adapter.count("self.llm_client.generate(") == 1
    assert "OpenAIClient" not in adapter
    assert ".generate(" not in factory
