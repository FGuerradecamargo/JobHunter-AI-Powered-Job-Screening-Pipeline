from models.application_contract import (
    ApplicationAnalysisSource,
)
from models.application_outcome import (
    ApplicationOutcome,
)
from models.interview_prep_contract import (
    InterviewPrepContract,
)
from models.profile_interpretation import (
    SourceEvidence,
)
from services.career_memory_source_builder import (
    CareerMemorySourceSnapshot,
)
from services.interview_prep_contract_service import (
    InterviewPrepContractService,
)
from services.legacy_interview_prep_compatibility import (
    build_legacy_active_interview_prep_contract,
)


class SourceRepository:
    def __init__(self, analysis=None):
        self.analysis = analysis or {
            "recommendation": "worth_second_look",
            "job_level": "mid-level",
            "core_requirements": [
                "Incident triage",
                "Operational documentation",
            ],
            "requirements_met": [
                "Case ownership",
            ],
            "strengths": [
                "Case ownership",
            ],
            "development_gaps": [
                "Cloud operations",
            ],
            "structural_gaps": [
                "Production incident response",
            ],
            "hard_conflicts": [],
        }

    def get_analysis_source(
        self,
        candidate_id,
        job_id,
    ):
        return ApplicationAnalysisSource(
            candidate_id=candidate_id,
            job_id=job_id,
            analysis_id="legacy-analysis-1",
            recommendation="worth_second_look",
            job={
                "id": job_id,
                "title": "Incident Response Analyst",
                "company": "Example Ltd",
            },
            analysis=self.analysis,
        )


class SnapshotRepository:
    def current_candidate(
        self,
        _candidate_id,
    ):
        return None


def profile_loader(
    candidate_id,
    _onboarding_repository,
    _career_update_repository,
):
    snapshot = CareerMemorySourceSnapshot(
        candidate_id=candidate_id,
        payload={
            "source_schema": "confirmed-onboarding-v1",
            "experiences": [
                {
                    "experience_id": "exp-1",
                    "company": "Current Company",
                    "start_date": "2024-01",
                    "end_date": None,
                }
            ],
        },
        source_signature="confirmed-source-signature",
    )

    evidence = (
        SourceEvidence(
            ref=(
                "professional_experience:"
                "exp-1:v3:q1"
            ),
            source_type="professional_experience",
            summary="Handled complex escalations end to end.",
        ),
        SourceEvidence(
            ref=(
                "candidate_preference:"
                + candidate_id
                + ":location"
            ),
            source_type="candidate_preference",
            summary='{"location": "Dublin"}',
        ),
    )

    return snapshot, evidence


def test_legacy_active_interview_builds_prep_contract_without_reclassifying_application():
    contract = (
        build_legacy_active_interview_prep_contract(
            "candidate-a",
            "job-1",
            interview_stage="interview",
            source_repository=SourceRepository(),
            snapshot_repository=SnapshotRepository(),
            profile_input_loader=profile_loader,
        )
    )

    assert contract.eligible is True
    assert contract.interview_stage == "interview"

    assert contract.target_requirements == [
        "Incident triage",
        "Operational documentation",
    ]

    assert contract.development_gaps == [
        "Cloud operations",
    ]

    assert contract.protected_structural_gaps == [
        "Production incident response",
    ]

    assert len(contract.authorized_evidence) == 1

    evidence = contract.authorized_evidence[0]

    assert (
        evidence.statement
        == "Handled complex escalations end to end."
    )

    assert (
        evidence.authority
        == "professional_fact"
    )

    assert (
        evidence.metadata["source_authority"]
        == "confirmed_user_record"
    )

    assert (
        contract.application_context_signature
        .startswith(
            "legacy-active-interview:"
        )
    )


def test_legacy_compatibility_refuses_current_hiring_case_payload_even_if_invalid():
    repository = SourceRepository(
        {
            "hiring_case": {},
            "core_requirements": [
                "Incident triage",
            ],
        }
    )

    try:
        build_legacy_active_interview_prep_contract(
            "candidate-a",
            "job-1",
            interview_stage="interview",
            source_repository=repository,
            snapshot_repository=SnapshotRepository(),
            profile_input_loader=profile_loader,
        )

    except ValueError as exc:
        assert "HiringCase" in str(exc)

    else:
        raise AssertionError(
            "Current HiringCase payload must fail closed."
        )


def test_legacy_compatibility_requires_active_interview():
    try:
        build_legacy_active_interview_prep_contract(
            "candidate-a",
            "job-1",
            interview_stage="",
            source_repository=SourceRepository(),
            snapshot_repository=SnapshotRepository(),
            profile_input_loader=profile_loader,
        )

    except ValueError as exc:
        assert "active interview" in str(exc)

    else:
        raise AssertionError(
            "Inactive applications must not use interview compatibility."
        )


class FailingApplicationContextService:
    def build(
        self,
        _candidate_id,
        _job_id,
    ):
        raise ValueError(
            "Application contract is not eligible."
        )


class OutcomeRepository:
    def __init__(
        self,
        *,
        active=True,
    ):
        self.active = active

    def get_application(
        self,
        candidate_id,
        job_id,
    ):
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "status": "applied",
        }

    def get(
        self,
        candidate_id,
        job_id,
    ):
        if not self.active:
            return None

        return ApplicationOutcome(
            candidate_id=candidate_id,
            job_id=job_id,
            interview_stage="interview",
        )


def compatibility_contract(
    candidate_id,
    job_id,
    *,
    interview_stage,
    application_final_status,
):
    return InterviewPrepContract(
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_id="legacy-analysis",
        application_context_signature="legacy-context",
        interview_stage=interview_stage,
        application_final_status=(
            application_final_status
        ),
        eligible=True,
        target_requirements=[
            "Incident triage",
        ],
        source_signature="legacy-signature",
    )


def test_contract_service_uses_legacy_boundary_only_for_active_interview():
    calls = []

    def builder(*args, **kwargs):
        calls.append(
            (args, kwargs)
        )

        return compatibility_contract(
            args[0],
            args[1],
            interview_stage=kwargs[
                "interview_stage"
            ],
            application_final_status=kwargs[
                "application_final_status"
            ],
        )

    service = InterviewPrepContractService(
        context_service=(
            FailingApplicationContextService()
        ),
        outcome_repository=(
            OutcomeRepository(active=True)
        ),
        legacy_contract_builder=builder,
    )

    contract = service.build(
        "candidate-a",
        "job-1",
    )

    assert contract.eligible
    assert contract.interview_stage == "interview"
    assert len(calls) == 1


def test_contract_service_does_not_use_legacy_boundary_without_interview():
    calls = []

    def builder(*args, **kwargs):
        calls.append(
            (args, kwargs)
        )

        return compatibility_contract(
            args[0],
            args[1],
            interview_stage="interview",
            application_final_status="",
        )

    service = InterviewPrepContractService(
        context_service=(
            FailingApplicationContextService()
        ),
        outcome_repository=(
            OutcomeRepository(active=False)
        ),
        legacy_contract_builder=builder,
    )

    try:
        service.build(
            "candidate-a",
            "job-1",
        )

    except ValueError as exc:
        assert (
            str(exc)
            == "Application contract is not eligible."
        )

    else:
        raise AssertionError(
            "Inactive application should remain fail-closed."
        )

    assert calls == []
