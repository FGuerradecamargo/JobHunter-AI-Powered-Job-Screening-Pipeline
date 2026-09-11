from models.candidate import Candidate
from models.career_update import CareerUpdate

from services.career_evidence_service import (
    CareerEvidenceService,
)


class FakeCandidateRepository:
    def __init__(
        self,
        candidate,
    ):
        self.candidate = candidate

    def get(
        self,
        candidate_id,
    ):
        if (
            self.candidate
            and self.candidate.id
            == candidate_id
        ):
            return self.candidate

        return None


class FakeCareerUpdateRepository:
    def __init__(
        self,
        updates=None,
    ):
        self.updates = (
            updates or []
        )

    def list_for_candidate(
        self,
        candidate_id,
    ):
        return [
            item
            for item in self.updates
            if (
                item.candidate_id
                == candidate_id
            )
        ]


def _candidate() -> Candidate:
    return Candidate(
        id="candidate-1",
        name="Test Candidate",
        current_role=(
            "Customer Operations"
        ),
        current_level="Specialist",
        professional_summary="",
        skills=[
            "Python",
        ],
        strengths=[
            "Stakeholder Communication",
        ],
        proven_capabilities=[
            "Complex customer escalation",
        ],
    )


def _service(
    *,
    candidate=None,
    updates=None,
    market_signals=None,
    outcomes=None,
):
    return CareerEvidenceService(
        candidate_repository=(
            FakeCandidateRepository(
                candidate
            )
        ),
        career_update_repository=(
            FakeCareerUpdateRepository(
                updates
            )
        ),
        market_signal_loader=(
            lambda candidate_id: (
                market_signals or []
            )
        ),
        outcome_loader=(
            lambda candidate_id: (
                outcomes or []
            )
        ),
    )


def test_builds_complete_candidate_evidence_view():
    service = _service(
        candidate=_candidate(),
        updates=[
            CareerUpdate(
                id="update-1",
                candidate_id="candidate-1",
                update_type="new_skill",
                description=(
                    "Completed SQL course"
                ),
                created_at="2026-09-01",
            )
        ],
        market_signals=[
            {
                "job_id": "job-1",
                "recommendation": (
                    "potential"
                ),
                "current_fit": 70,
                "market_signal": {
                    "role_family": (
                        "Product Operations"
                    ),
                    "market_strengths": [
                        "Stakeholder Communication",
                    ],
                    "best_match_blockers": [
                        "SQL",
                    ],
                    "what_would_raise_fit": [
                        "Demonstrated SQL projects",
                    ],
                },
            },
            {
                "job_id": "job-2",
                "recommendation": (
                    "good_opportunity"
                ),
                "current_fit": 68,
                "market_signal": {
                    "role_family": (
                        "Product Operations"
                    ),
                    "market_strengths": [
                        "Stakeholder Communication",
                    ],
                    "best_match_blockers": [
                        "SQL",
                    ],
                    "what_would_raise_fit": [
                        "Demonstrated SQL projects",
                    ],
                },
            },
        ],
        outcomes=[
            {
                "job_id": "job-3",
                "final_status": (
                    "interview"
                ),
                "interview_stage": (
                    "screen"
                ),
                "outcome_date": (
                    "2026-09-10"
                ),
            }
        ],
    )

    result = service.build(
        "candidate-1"
    )

    assert result[
        "candidate_id"
    ] == "candidate-1"

    assert result[
        "counts"
    ]["market_sources"] == 2

    assert result[
        "counts"
    ]["outcomes"] == 1

    blocker = next(
        item
        for item in result[
            "market_signals"
        ]
        if (
            item.signal_type
            == "best_match_blocker"
            and item.statement
            == "SQL"
        )
    )

    assert blocker.independent_sources == 2
    assert blocker.sample_size == 2
    assert blocker.frequency == 1.0
    assert blocker.confidence == "medium"

    assert any(
        item.evidence_type
        == "career_update"
        and item.statement
        == "Completed SQL course"
        for item in result[
            "records"
        ]
    )

    assert any(
        item.evidence_type
        == "application_outcome"
        and item.statement
        == "interview"
        for item in result[
            "records"
        ]
    )


def test_candidate_isolation_is_preserved():
    service = _service(
        candidate=_candidate(),
        updates=[
            CareerUpdate(
                id="update-other",
                candidate_id="candidate-2",
                update_type="new_skill",
                description=(
                    "Should not be visible"
                ),
            )
        ],
    )

    result = service.build(
        "candidate-1"
    )

    assert not any(
        item.statement
        == "Should not be visible"
        for item in result[
            "records"
        ]
    )


def test_missing_candidate_is_rejected():
    service = _service(
        candidate=None,
    )

    try:
        service.build(
            "candidate-1"
        )
    except ValueError as exc:
        assert (
            "Candidate was not found"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_empty_candidate_id_is_rejected():
    service = _service(
        candidate=_candidate(),
    )

    try:
        service.build(
            "   "
        )
    except ValueError as exc:
        assert (
            "candidate_id must be non-empty"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_empty_market_history_is_valid():
    service = _service(
        candidate=_candidate(),
    )

    result = service.build(
        "candidate-1"
    )

    assert result[
        "market_signals"
    ] == []

    assert result[
        "counts"
    ]["market_sources"] == 0

    assert result[
        "counts"
    ]["outcomes"] == 0


def test_all_external_loaders_are_scoped_to_requested_candidate():
    calls = {"market": [], "outcomes": []}
    service = CareerEvidenceService(
        candidate_repository=FakeCandidateRepository(_candidate()),
        career_update_repository=FakeCareerUpdateRepository(),
        market_signal_loader=lambda candidate_id: (
            calls["market"].append(candidate_id) or []
        ),
        outcome_loader=lambda candidate_id: (
            calls["outcomes"].append(candidate_id) or []
        ),
    )

    service.build("candidate-1")

    assert calls == {
        "market": ["candidate-1"],
        "outcomes": ["candidate-1"],
    }
