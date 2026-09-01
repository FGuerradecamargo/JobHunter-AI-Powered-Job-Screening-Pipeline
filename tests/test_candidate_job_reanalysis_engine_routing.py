import pytest

import services.candidate_job_analysis_service as module

from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
)


def test_analyze_pending_uses_discovery_selector_and_shared_engine(
    monkeypatch,
):
    service = object.__new__(
        CandidateJobAnalysisService
    )

    rows = [
        {
            "id": "new-job-1",
        },
    ]

    selector_call = {}
    engine_call = {}

    def fake_selector(
        **kwargs,
    ):
        selector_call.update(
            kwargs
        )

        return rows

    def fake_engine(
        **kwargs,
    ):
        engine_call.update(
            kwargs
        )

        return {
            "mode": "discovery",
        }

    monkeypatch.setattr(
        module,
        "list_pending_candidate_jobs",
        fake_selector,
    )

    service._run_candidate_job_analysis = (
        fake_engine
    )

    budget = object()

    result = service.analyze_pending(
        candidate_id="candidate-a",
        limit=7,
        target_opportunities=5,
        ai_budget=budget,
        job_ids=[
            "new-job-1",
        ],
    )

    assert selector_call == {
        "candidate_id": "candidate-a",
        "limit": 7,
        "job_ids": [
            "new-job-1",
        ],
    }

    assert engine_call[
        "candidate_id"
    ] == "candidate-a"

    assert engine_call[
        "source_rows"
    ] is rows

    assert engine_call[
        "target_opportunities"
    ] == 5

    assert engine_call[
        "ai_budget"
    ] is budget

    assert (
        engine_call[
            "preserve_existing_lifecycle"
        ]
        is False
    )

    assert result == {
        "mode": "discovery",
    }


def test_reanalyze_stale_uses_granular_signatures_and_shared_engine(
    monkeypatch,
):
    service = object.__new__(
        CandidateJobAnalysisService
    )

    candidate = object()
    objective = object()
    updates = [
        object(),
    ]

    class CandidateRepository:
        def get(
            self,
            candidate_id,
        ):
            assert (
                candidate_id
                == "candidate-a"
            )

            return candidate

    class ObjectiveRepository:
        def get_active(
            self,
            candidate_id,
        ):
            assert (
                candidate_id
                == "candidate-a"
            )

            return objective

    class UpdateRepository:
        def list_for_candidate(
            self,
            candidate_id,
        ):
            assert (
                candidate_id
                == "candidate-a"
            )

            return updates

    service.candidate_repository = (
        CandidateRepository()
    )

    service.career_objective_repository = (
        ObjectiveRepository()
    )

    service.career_update_repository = (
        UpdateRepository()
    )

    monkeypatch.setattr(
        module,
        "build_candidate_evidence_signature",
        lambda candidate_arg, updates_arg: (
            "current-e"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_candidate_direction_signature",
        lambda candidate_arg,
        objective_arg,
        updates_arg: (
            "current-d"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_candidate_constraint_signature",
        lambda candidate_arg: (
            "current-c"
        ),
    )

    rows = [
        {
            "id": "stale-job-1",
            "opportunity_state": "active",
            "status": "in_review",
            "reanalysis_reasons": [
                "direction",
            ],
        },
    ]

    selector_call = {}
    engine_call = {}

    def fake_selector(
        **kwargs,
    ):
        selector_call.update(
            kwargs
        )

        return rows

    def fake_engine(
        **kwargs,
    ):
        engine_call.update(
            kwargs
        )

        return {
            "mode": "reanalysis",
        }

    monkeypatch.setattr(
        module,
        "list_candidate_jobs_for_reanalysis",
        fake_selector,
    )

    service._run_candidate_job_analysis = (
        fake_engine
    )

    budget = object()

    result = service.reanalyze_stale(
        candidate_id="candidate-a",
        limit=12,
        ai_budget=budget,
        job_ids=[
            "stale-job-1",
        ],
    )

    assert selector_call == {
        "candidate_id": "candidate-a",
        "evidence_signature": "current-e",
        "direction_signature": "current-d",
        "constraint_signature": "current-c",
        "limit": 12,
        "job_ids": [
            "stale-job-1",
        ],
    }

    assert engine_call[
        "candidate_id"
    ] == "candidate-a"

    assert engine_call[
        "source_rows"
    ] is rows

    assert (
        engine_call[
            "target_opportunities"
        ]
        is None
    )

    assert engine_call[
        "ai_budget"
    ] is budget

    assert (
        engine_call[
            "preserve_existing_lifecycle"
        ]
        is True
    )

    assert result == {
        "mode": "reanalysis",
    }


def test_reanalyze_stale_refuses_missing_candidate(
    monkeypatch,
):
    service = object.__new__(
        CandidateJobAnalysisService
    )

    class CandidateRepository:
        def get(
            self,
            candidate_id,
        ):
            return None

    service.candidate_repository = (
        CandidateRepository()
    )

    called = {
        "selector": False,
    }

    def fake_selector(
        **kwargs,
    ):
        called["selector"] = True

        return []

    monkeypatch.setattr(
        module,
        "list_candidate_jobs_for_reanalysis",
        fake_selector,
    )

    with pytest.raises(
        ValueError,
        match="Candidate not found",
    ):
        service.reanalyze_stale(
            candidate_id="missing",
        )

    assert (
        called["selector"]
        is False
    )



def test_reanalysis_ai_reject_preserves_active_lifecycle(
    monkeypatch,
):
    service = object.__new__(
        CandidateJobAnalysisService
    )

    candidate = object()
    profile = object()

    class CandidateRepository:
        def get(
            self,
            candidate_id,
        ):
            assert candidate_id == "candidate-a"

            return candidate


    class ObjectiveRepository:
        def get_active(
            self,
            candidate_id,
        ):
            return None


    class UpdateRepository:
        def list_for_candidate(
            self,
            candidate_id,
        ):
            return []


    class FakeJobProfile:
        summary = "Test role"
        seniority = "mid"
        must_have_capabilities = []
        nice_to_have_capabilities = []
        key_responsibilities = []
        tools_and_technologies = []
        required_qualifications = []
        stakeholders_and_collaboration = []
        important_details = []
        role_context = ""
        role_family = "Technical Support"


    class JobProfileManager:
        def get_or_create(
            self,
            job,
        ):
            return FakeJobProfile()


    class HardFilter:
        def __init__(
            self,
            candidate_profile,
        ):
            assert candidate_profile is profile

        def analyze(
            self,
            job,
            job_profile,
        ):
            return {
                "rejected": False,
                "reasons": [],
            }


    class FakeAIResult:
        def __init__(
            self,
            job_id,
        ):
            self.job_id = job_id


    class AIService:
        def analyze_batch(
            self,
            *,
            items,
            candidate_profile,
            career_memory,
        ):
            assert candidate_profile is profile

            assert career_memory == {
                "continuity_note": (
                    "ACTIVE_REANALYSIS_MEMORY"
                ),
            }

            assert len(items) == 1

            return [
                FakeAIResult(
                    items[0][0].id
                ),
            ]


    service.candidate_repository = (
        CandidateRepository()
    )

    service.career_objective_repository = (
        ObjectiveRepository()
    )

    service.career_update_repository = (
        UpdateRepository()
    )

    service.job_profile_manager = (
        JobProfileManager()
    )

    service.ai_service = AIService()

    service._load_candidate_career_memory = (
        lambda candidate_id: {
            "continuity_note": (
                "ACTIVE_REANALYSIS_MEMORY"
            ),
        }
    )


    monkeypatch.setattr(
        module,
        "candidate_to_profile",
        lambda *args, **kwargs: profile,
    )

    monkeypatch.setattr(
        module,
        "HardFilterAnalyzer",
        HardFilter,
    )

    monkeypatch.setattr(
        module,
        "build_candidate_signature",
        lambda *args, **kwargs: (
            "candidate-signature"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_candidate_evidence_signature",
        lambda *args, **kwargs: (
            "new-e"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_candidate_direction_signature",
        lambda *args, **kwargs: (
            "new-d"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_candidate_constraint_signature",
        lambda *args, **kwargs: (
            "new-c"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_job_signature",
        lambda job: "job-signature",
    )

    # The production Engine calls dataclasses.asdict().
    # We only need a controlled validated-AI payload here.
    monkeypatch.setattr(
        module,
        "asdict",
        lambda ai_result: {
            "job_id": ai_result.job_id,
            "recommendation": "reject",
            "competitive_status": (
                "not_competitive_now"
            ),
            "current_fit": 25,
            "growth_value": 10,
            "direction_alignment": "low",
            "tailored_cv": "must-be-cleared",
            "interview_prep": "must-be-cleared",
            "market_signal": "",
        },
    )


    persisted = []


    def fake_save_candidate_job_analysis(
        **kwargs,
    ):
        persisted.append(
            kwargs
        )


    monkeypatch.setattr(
        module,
        "save_candidate_job_analysis_with_run",
        fake_save_candidate_job_analysis,
    )


    source_rows = [
        {
            "id": "active-job-1",
            "raw_text": "",
            "url": (
                "https://example.test/"
                "active-job-1"
            ),
            "title": (
                "Technical Support Engineer"
            ),
            "company": "Example",
            "location": "Ireland",
            "remote": True,
            "salary": "",
            "easy_apply": False,
            "description": (
                "Complete test job description."
            ),

            # Existing candidate lifecycle:
            "analysis_state": "analyzed",
            "opportunity_state": "active",
            "status": "in_review",

            "evidence_signature": "old-e",
            "direction_signature": "old-d",
            "constraint_signature": "old-c",

            "reanalysis_reasons": [
                "evidence",
                "direction",
                "constraint",
            ],
        },
    ]


    result = (
        service._run_candidate_job_analysis(
            candidate_id="candidate-a",
            source_rows=source_rows,
            preserve_existing_lifecycle=True,
        )
    )


    assert len(persisted) == 1

    saved = persisted[0]


    # The analytical result changed to reject...
    assert (
        saved["analysis"][
            "recommendation"
        ]
        == "reject"
    )

    assert (
        saved["analysis"][
            "tailored_cv"
        ]
        is None
    )

    assert (
        saved["analysis"][
            "interview_prep"
        ]
        is None
    )

    # ...but the user's active lifecycle survives.
    assert saved["status"] == "in_review"

    assert (
        saved["opportunity_state"]
        == "active"
    )

    # Current signatures replace stale signatures.
    assert (
        saved["evidence_signature"]
        == "new-e"
    )

    assert (
        saved["direction_signature"]
        == "new-d"
    )

    assert (
        saved["constraint_signature"]
        == "new-c"
    )

    assert result["selected"] == 1
    assert result["analyzed"] == 1
    assert result["ai_rejected"] == 1
    assert result["failed"] == 0
