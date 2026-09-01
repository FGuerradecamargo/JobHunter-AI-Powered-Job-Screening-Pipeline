from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
)


class FakeCareerMemoryRepository:
    def __init__(
        self,
        snapshots,
    ):
        self.snapshots = snapshots
        self.requested_candidate_ids = []

    def get_snapshot(
        self,
        candidate_id,
    ):
        self.requested_candidate_ids.append(
            candidate_id
        )

        return self.snapshots.get(
            candidate_id
        )


def _service_with_repository(
    repository,
):
    # Avoid constructing OpenAI clients and the
    # rest of the production service graph.
    service = object.__new__(
        CandidateJobAnalysisService
    )

    service.career_memory_repository = (
        repository
    )

    return service


def test_career_memory_read_is_candidate_scoped():
    repository = (
        FakeCareerMemoryRepository(
            {
                "candidate-a": {
                    "memory": {
                        "continuity_note": (
                            "MEMORY_A_ONLY"
                        ),
                    },
                },
                "candidate-b": {
                    "memory": {
                        "continuity_note": (
                            "MEMORY_B_ONLY"
                        ),
                    },
                },
            }
        )
    )

    service = _service_with_repository(
        repository
    )

    memory_a = (
        service._load_candidate_career_memory(
            "candidate-a"
        )
    )

    memory_b = (
        service._load_candidate_career_memory(
            "candidate-b"
        )
    )

    assert (
        memory_a["continuity_note"]
        == "MEMORY_A_ONLY"
    )

    assert (
        memory_b["continuity_note"]
        == "MEMORY_B_ONLY"
    )

    assert (
        "MEMORY_B_ONLY"
        not in str(memory_a)
    )

    assert (
        "MEMORY_A_ONLY"
        not in str(memory_b)
    )

    assert (
        repository.requested_candidate_ids
        == [
            "candidate-a",
            "candidate-b",
        ]
    )


def test_missing_career_memory_returns_empty_context():
    repository = (
        FakeCareerMemoryRepository({})
    )

    service = _service_with_repository(
        repository
    )

    memory = (
        service._load_candidate_career_memory(
            "candidate-without-memory"
        )
    )

    assert memory == {}

    assert (
        repository.requested_candidate_ids
        == [
            "candidate-without-memory"
        ]
    )


def test_malformed_persisted_memory_fails_safe():
    repository = (
        FakeCareerMemoryRepository(
            {
                "candidate-a": {
                    "memory": [
                        "invalid",
                        "memory",
                    ],
                },
            }
        )
    )

    service = _service_with_repository(
        repository
    )

    memory = (
        service._load_candidate_career_memory(
            "candidate-a"
        )
    )

    assert memory == {}



def test_analyze_pending_forwards_same_candidates_memory_to_batch(
    monkeypatch,
):
    from models.candidate_profile import (
        CandidateProfile,
    )

    import services.candidate_job_analysis_service as module

    captured = {}


    class FakeCandidateRepository:
        def get(
            self,
            candidate_id,
        ):
            assert candidate_id == "candidate-a"

            return object()


    class FakeObjectiveRepository:
        def get_active(
            self,
            candidate_id,
        ):
            assert candidate_id == "candidate-a"

            return None


    class FakeUpdateRepository:
        def list_for_candidate(
            self,
            candidate_id,
        ):
            assert candidate_id == "candidate-a"

            return []


    class FakeMemoryRepository:
        def __init__(self):
            self.calls = []

        def get_snapshot(
            self,
            candidate_id,
        ):
            self.calls.append(
                candidate_id
            )

            if candidate_id != "candidate-a":
                raise AssertionError(
                    "Cross-candidate Career Memory read."
                )

            return {
                "memory": {
                    "continuity_note": (
                        "MEMORY_A_PIPELINE"
                    ),
                },
            }


    class FakeHardFilter:
        def __init__(
            self,
            profile,
        ):
            captured[
                "hard_filter_profile"
            ] = profile

        def analyze(
            self,
            job,
            job_profile,
        ):
            return {
                "rejected": False,
                "reasons": [],
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


    class FakeJobProfileManager:
        def get_or_create(
            self,
            job,
        ):
            return FakeJobProfile()


    class CapturingAIService:
        def analyze_batch(
            self,
            *,
            items,
            candidate_profile,
            career_memory,
        ):
            captured["items"] = items

            captured[
                "candidate_profile"
            ] = candidate_profile

            captured[
                "career_memory"
            ] = career_memory

            # Stop immediately after proving the
            # production handoff. analyze_pending()
            # intentionally catches batch failures.
            raise RuntimeError(
                "stop after batch capture"
            )


    memory_repository = (
        FakeMemoryRepository()
    )

    service = object.__new__(
        module.CandidateJobAnalysisService
    )

    service.candidate_repository = (
        FakeCandidateRepository()
    )

    service.career_objective_repository = (
        FakeObjectiveRepository()
    )

    service.career_update_repository = (
        FakeUpdateRepository()
    )

    service.career_memory_repository = (
        memory_repository
    )

    service.job_profile_manager = (
        FakeJobProfileManager()
    )

    service.ai_service = (
        CapturingAIService()
    )

    # Description is already present, so enrichment
    # and network-related behavior are never needed.
    monkeypatch.setattr(
        module,
        "list_pending_candidate_jobs",
        lambda **kwargs: [
            {
                "id": "job-a-1",
                "raw_text": "",
                "url": (
                    "https://example.test/job-a-1"
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
                    "Normal test job description."
                ),
            }
        ],
    )

    monkeypatch.setattr(
        module,
        "candidate_to_profile",
        lambda *args, **kwargs: (
            CandidateProfile(
                current_roles=[
                    "Operations Specialist"
                ],
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "HardFilterAnalyzer",
        FakeHardFilter,
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
            "evidence-signature"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_candidate_direction_signature",
        lambda *args, **kwargs: (
            "direction-signature"
        ),
    )

    monkeypatch.setattr(
        module,
        "build_candidate_constraint_signature",
        lambda *args, **kwargs: (
            "constraint-signature"
        ),
    )


    result = service.analyze_pending(
        candidate_id="candidate-a",
        limit=1,
    )


    # The snapshot must be requested using the exact
    # candidate that owns this scan.
    assert (
        memory_repository.calls
        == [
            "candidate-a",
        ]
    )

    # The exact candidate-scoped persisted memory
    # reaches the production batch call.
    assert (
        captured[
            "career_memory"
        ][
            "continuity_note"
        ]
        == "MEMORY_A_PIPELINE"
    )

    assert (
        "MEMORY_A_PIPELINE"
        in str(
            captured[
                "career_memory"
            ]
        )
    )

    assert (
        len(
            captured["items"]
        )
        == 1
    )

    assert (
        captured[
            "items"
        ][0][0].id
        == "job-a-1"
    )

    # Candidate Profile remains a separate object.
    assert isinstance(
        captured[
            "candidate_profile"
        ],
        CandidateProfile,
    )

    assert (
        "MEMORY_A_PIPELINE"
        not in str(
            captured[
                "candidate_profile"
            ]
        )
    )

    # Fake AI stops after capture. The production
    # service should contain that batch failure rather
    # than leaking it out of analyze_pending().
    assert result["failed"] == 1

    assert any(
        (
            error.get("job_id")
            == "job-a-1"
        )
        for error
        in result["errors"]
    )
