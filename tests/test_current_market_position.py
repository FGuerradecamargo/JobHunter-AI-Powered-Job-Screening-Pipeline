import pytest

from models.career_evidence import CareerEvidence
from models.career_objective import CareerObjective
from models.objective_profile import ObjectiveProfile
from services.current_market_position_builder import (
    build_current_market_position,
)
from services.current_market_position_service import (
    CurrentMarketPositionService,
)


def _record(
    evidence_id,
    job_id,
    role_family,
    recommendation,
    current_fit,
):
    return CareerEvidence(
        evidence_id=evidence_id,
        evidence_type="market_signal",
        signal_type="role_family",
        source_ref=f"job:{job_id}",
        statement=role_family,
        role_family=role_family,
        authority="market_evidence",
        metadata={
            "job_id": job_id,
            "recommendation": recommendation,
            "current_fit": current_fit,
        },
    )


def _position():
    records = [
        _record("e1", "1", "Product Operations", "best_match", 80),
        _record("e2", "2", "product operations", "best_match", 90),
        _record("e3", "3", "Data Operations", "reject", 60),
        _record("e3-duplicate", "3", "Data Operations", "reject", 60),
        _record("e4", "4", "Legacy Support", "reject", 10),
        _record("e5", "5", "Sales Operations", "potential", 70),
    ]
    return build_current_market_position(
        candidate_id="candidate-a",
        evidence_records=records,
        target_role_families=[
            "Product Operations",
            "Data Operations",
            "Future AI Operations",
        ],
    )


def test_competitive_roles_are_supported_by_observed_jobs():
    position = _position()
    product = next(
        item
        for item in position.competitive_role_families
        if item.role_family.casefold() == "product operations"
    )

    assert product.authority == "market_evidence"
    assert product.independent_sources == 2
    assert product.source_refs == ["job:1", "job:2"]
    assert product.evidence_refs == ["e1", "e2"]
    assert product.sample_size == 5
    assert product.frequency == 0.4
    assert product.confidence == "medium"


def test_near_market_role_is_a_bridge_and_deduplicates_job():
    position = _position()
    bridge = position.bridge_role_families[0]

    assert bridge.role_family == "Data Operations"
    assert bridge.independent_sources == 1
    assert bridge.source_refs == ["job:3"]
    assert bridge.evidence_refs == ["e3", "e3-duplicate"]
    assert all(
        item.role_family != "Legacy Support"
        for item in position.bridge_role_families
    )


def test_explicit_targets_remain_separate_from_competitiveness():
    position = _position()
    targets = {
        item.role_family: item
        for item in position.target_role_families
    }
    competitive = {
        item.role_family.casefold()
        for item in position.competitive_role_families
    }

    assert "Future AI Operations" in targets
    assert targets["Future AI Operations"].authority == "user_direction"
    assert targets["Future AI Operations"].evidence_refs == []
    assert "future ai operations" not in competitive
    assert "sales operations" in competitive
    assert "Sales Operations" not in targets


def test_counts_and_average_use_aligned_viable_surface():
    position = _position()

    assert position.best_match_count == 2
    assert position.near_match_count == 1
    assert position.sample_size == 5
    assert position.fit_sample_size == 4
    assert position.average_fit == 75.0


def test_empty_market_history_is_valid_checkpoint():
    position = build_current_market_position(
        candidate_id="candidate-a",
        evidence_records=[],
        target_role_families=["Future AI Operations"],
    )

    assert position.sample_size == 0
    assert position.average_fit is None
    assert position.best_match_count == 0
    assert position.near_match_count == 0
    assert position.competitive_role_families == []
    assert position.bridge_role_families == []
    assert position.target_role_families[0].confidence == "low"


class FakeEvidenceService:
    def __init__(self, candidate_id="candidate-a"):
        self.candidate_id = candidate_id
        self.calls = []

    def build(self, candidate_id):
        self.calls.append(candidate_id)
        return {
            "candidate_id": self.candidate_id,
            "records": [],
        }


class FakeObjectiveRepository:
    def __init__(self, objective=None):
        self.objective = objective

    def get_active(self, candidate_id):
        return self.objective


class FakeProfileRepository:
    def __init__(self, profile=None):
        self.profile = profile

    def get_active_for_candidate(self, candidate_id):
        return self.profile


def _service(
    *,
    evidence_candidate_id="candidate-a",
    objective=None,
    profile=None,
):
    return CurrentMarketPositionService(
        evidence_service=FakeEvidenceService(evidence_candidate_id),
        objective_repository=FakeObjectiveRepository(objective),
        objective_profile_repository=FakeProfileRepository(profile),
    )


def test_service_uses_only_explicit_candidate_direction():
    service = _service(
        objective=CareerObjective(
            id="objective-a",
            candidate_id="candidate-a",
            title="Direction",
            description="Explicit direction",
            desired_role_families=["Product Operations"],
        ),
        profile=ObjectiveProfile(
            candidate_id="candidate-a",
            objective_id="objective-a",
            competitive_role_families=["Must not become target"],
            target_role_families=["Data Operations"],
        ),
    )

    position = service.build("candidate-a")

    assert [
        item.role_family
        for item in position.target_role_families
    ] == ["Data Operations", "Product Operations"]


@pytest.mark.parametrize(
    ("evidence_candidate_id", "objective_candidate_id", "profile_candidate_id"),
    [
        ("candidate-b", "candidate-a", "candidate-a"),
        ("candidate-a", "candidate-b", "candidate-a"),
        ("candidate-a", "candidate-a", "candidate-b"),
    ],
)
def test_service_rejects_cross_candidate_dependencies(
    evidence_candidate_id,
    objective_candidate_id,
    profile_candidate_id,
):
    service = _service(
        evidence_candidate_id=evidence_candidate_id,
        objective=CareerObjective(
            id="objective-a",
            candidate_id=objective_candidate_id,
            title="Direction",
            description="Direction",
        ),
        profile=ObjectiveProfile(
            candidate_id=profile_candidate_id,
            objective_id="objective-a",
        ),
    )

    with pytest.raises(PermissionError):
        service.build("candidate-a")


def test_candidate_id_is_required():
    with pytest.raises(ValueError, match="candidate_id must be non-empty"):
        _service().build("   ")
