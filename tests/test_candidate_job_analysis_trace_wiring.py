import services.candidate_job_analysis_service as module

from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
)


SOURCE_ROW = {
    "id": "job-1",
    "raw_text": "",
    "url": "https://example.test/job-1",
    "title": "Technical Support Engineer",
    "company": "Example",
    "location": "Ireland",
    "remote": True,
    "salary": "",
    "easy_apply": False,
    "description": (
        "Complete candidate-job traceability test role."
    ),
    "analysis_state": "analyzed",
    "opportunity_state": "active",
    "status": "in_review",
    "evidence_signature": "old-e",
    "direction_signature": "old-d",
    "constraint_signature": "old-c",
    "reanalysis_reasons": [
        "direction",
        "evidence",
    ],
}


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


class FakeAIResult:
    def __init__(
        self,
        job_id,
    ):
        self.job_id = job_id


def _build_service(
    monkeypatch,
    *,
    hard_rejected=False,
    ai_error=None,
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
            assert candidate_id == "candidate-a"
            return None

    class UpdateRepository:
        def list_for_candidate(
            self,
            candidate_id,
        ):
            assert candidate_id == "candidate-a"
            return []

    class MemoryRepository:
        def get_snapshot(
            self,
            candidate_id,
        ):
            assert candidate_id == "candidate-a"

            return {
                "memory_version": 7,
                "memory_schema_version": (
                    "career-memory-v1"
                ),
                "source_signature": (
                    "memory-source-v7"
                ),
                "interpreted_source_signature": (
                    "memory-source-v6"
                ),
                "memory": {
                    "continuity_note": (
                        "TRACE_MEMORY"
                    ),
                },
            }

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
            if hard_rejected:
                return {
                    "rejected": True,
                    "reasons": [
                        "Hard constraint",
                    ],
                }

            return {
                "rejected": False,
                "reasons": [],
            }

    class AIService:
        def analyze_batch(
            self,
            *,
            items,
            candidate_profile,
            career_memory,
        ):
            assert candidate_profile is profile

            assert dict(
                career_memory
            ) == {
                "continuity_note": (
                    "TRACE_MEMORY"
                ),
            }

            if ai_error is not None:
                raise ai_error

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

    service.career_memory_repository = (
        MemoryRepository()
    )

    service.job_profile_manager = (
        JobProfileManager()
    )

    service.ai_service = AIService()

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
        lambda *args, **kwargs: "new-e",
    )

    monkeypatch.setattr(
        module,
        "build_candidate_direction_signature",
        lambda *args, **kwargs: "new-d",
    )

    monkeypatch.setattr(
        module,
        "build_candidate_constraint_signature",
        lambda *args, **kwargs: "new-c",
    )

    monkeypatch.setattr(
        module,
        "build_job_signature",
        lambda job: "job-signature",
    )

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
            "tailored_cv": "must-clear",
            "interview_prep": "must-clear",
            "market_signal": "",
        },
    )

    return service


def test_reanalysis_completed_run_carries_full_provenance(
    monkeypatch,
):
    service = _build_service(
        monkeypatch
    )

    completed = []

    monkeypatch.setattr(
        module,
        "save_candidate_job_analysis_with_run",
        lambda **kwargs: completed.append(
            kwargs
        ),
    )

    monkeypatch.setattr(
        module,
        "append_candidate_job_analysis_run",
        lambda **kwargs: (
            (_ for _ in ()).throw(
                AssertionError(
                    "Unexpected failed run."
                )
            )
        ),
    )

    result = service._run_candidate_job_analysis(
        candidate_id="candidate-a",
        source_rows=[
            dict(SOURCE_ROW)
        ],
        preserve_existing_lifecycle=True,
        scan_id="scan-fixed",
        run_mode="reanalysis",
    )

    assert len(completed) == 1

    saved = completed[0]

    assert saved["scan_id"] == "scan-fixed"

    assert saved["batch_id"].startswith(
        "candidate_job_batch_"
    )

    assert saved["run_mode"] == "reanalysis"

    assert saved["trigger_reasons"] == [
        "direction",
        "evidence",
    ]

    assert (
        saved["job_profile_version"]
        == module.JOB_PROFILE_VERSION
    )

    assert saved["career_memory_version"] == 7

    assert (
        saved["career_memory_schema_version"]
        == "career-memory-v1"
    )

    assert (
        saved["career_memory_source_signature"]
        == "memory-source-v7"
    )

    assert (
        saved[
            "career_memory_"
            "interpreted_source_signature"
        ]
        == "memory-source-v6"
    )

    assert saved["evidence_signature"] == "new-e"
    assert saved["direction_signature"] == "new-d"
    assert saved["constraint_signature"] == "new-c"

    # Existing user lifecycle survives reanalysis.
    assert saved["status"] == "in_review"
    assert saved["opportunity_state"] == "active"

    # New analytical result is still reject.
    assert (
        saved["analysis"]["recommendation"]
        == "reject"
    )

    assert result["scan_id"] == "scan-fixed"
    assert result["run_mode"] == "reanalysis"
    assert result["analyzed"] == 1


def test_batch_ai_failure_creates_failed_run_without_current_write(
    monkeypatch,
):
    service = _build_service(
        monkeypatch,
        ai_error=RuntimeError(
            "simulated batch failure"
        ),
    )

    failures = []

    monkeypatch.setattr(
        module,
        "save_candidate_job_analysis_with_run",
        lambda **kwargs: (
            (_ for _ in ()).throw(
                AssertionError(
                    "Current state must not be written."
                )
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "append_candidate_job_analysis_run",
        lambda **kwargs: failures.append(
            kwargs
        ),
    )

    discovery_row = dict(
        SOURCE_ROW
    )

    discovery_row.pop(
        "reanalysis_reasons",
        None,
    )

    discovery_row["opportunity_state"] = "none"
    discovery_row["analysis_state"] = "pending"

    result = service._run_candidate_job_analysis(
        candidate_id="candidate-a",
        source_rows=[
            discovery_row
        ],
        preserve_existing_lifecycle=False,
        scan_id="scan-failure",
        run_mode="discovery",
    )

    assert len(failures) == 1

    failed = failures[0]

    assert failed["scan_id"] == "scan-failure"

    assert failed["batch_id"].startswith(
        "candidate_job_batch_"
    )

    assert failed["run_mode"] == "discovery"

    assert failed["trigger_reasons"] == [
        "initial_analysis",
    ]

    assert failed["result_state"] == "failed"
    assert failed["result_stage"] == "batch_ai"

    assert (
        "simulated batch failure"
        in failed["error_text"]
    )

    assert failed["career_memory_version"] == 7

    assert result["analyzed"] == 0
    assert result["failed"] == 1


def test_hard_filter_completed_run_uses_preparation_batch(
    monkeypatch,
):
    service = _build_service(
        monkeypatch,
        hard_rejected=True,
    )

    completed = []

    monkeypatch.setattr(
        module,
        "save_candidate_job_analysis_with_run",
        lambda **kwargs: completed.append(
            kwargs
        ),
    )

    monkeypatch.setattr(
        module,
        "append_candidate_job_analysis_run",
        lambda **kwargs: (
            (_ for _ in ()).throw(
                AssertionError(
                    "Hard reject should complete, "
                    "not fail."
                )
            )
        ),
    )

    row = dict(
        SOURCE_ROW
    )

    row.pop(
        "reanalysis_reasons",
        None,
    )

    row["opportunity_state"] = "none"
    row["analysis_state"] = "pending"

    result = service._run_candidate_job_analysis(
        candidate_id="candidate-a",
        source_rows=[
            row
        ],
        preserve_existing_lifecycle=False,
        scan_id="scan-hard-filter",
        run_mode="discovery",
    )

    assert len(completed) == 1

    saved = completed[0]

    assert saved["scan_id"] == (
        "scan-hard-filter"
    )

    assert saved["batch_id"].startswith(
        "candidate_job_batch_"
    )

    assert saved["trigger_reasons"] == [
        "initial_analysis",
    ]

    assert saved["result_stage"] == "hard_filter"

    assert (
        saved["analysis"]["rule_rejection_type"]
        == "hard_filter"
    )

    assert result["hard_rejected"] == 1
    assert result["analyzed"] == 1
    assert result["failed"] == 0
