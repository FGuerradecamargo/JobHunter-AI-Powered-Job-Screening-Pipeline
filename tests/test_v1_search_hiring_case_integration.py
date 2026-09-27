import json
import socket
from types import SimpleNamespace

import pytest

from models.profile_interpretation import JobProfileDraft, InterpretedJobNeed, InterpretationAuthority
from models.hiring_case import RequirementImportance
from services import database
from services.ai.ai_recommendation_service import AIRecommendationService
from services.candidate_job_analysis_service import CandidateJobAnalysisService
from services.candidate_repository import CandidateRepository
from services.career_objective_repository import CareerObjectiveRepository
from services.career_update_repository import CareerUpdateRepository
from services.career_memory_repository import CareerMemoryRepository
from services.job_profile_manager import JobProfileManager
from tests.test_workpilot_v1_onboarding_persistence import repo
from tests.test_v1_runtime_candidate_profile import Client, service as generation_service
from tests.test_v1_job_observation_authority import ingest, job


class RelationshipClient:
    def __init__(self, unknown=False):
        self.calls = 0
        self.unknown = unknown

    def generate(self, prompt):
        self.calls += 1
        requests = json.loads(prompt.rsplit("\n", 1)[1])
        results = []
        for request in requests:
            cap = request["candidate_profile"]["capabilities"][0]
            results.append({"job_id": request["job_id"], "semantic": {"links": [{
                "need_id": "need", "candidate_capability_id": cap["capability_id"],
                "assessment": "evidence_missing" if self.unknown else "proven",
                "evidence_refs": [] if self.unknown else cap["evidence_refs"],
                "confidence": "unknown" if self.unknown else "high",
                "reason_code": "uncertain" if self.unknown else "direct_support",
                "needs_evidence": self.unknown,
            }]}, "opportunity": {"signals": [{
                "kind": fact["kind"], "factual_state": fact["state"],
                "state": "positive" if fact["state"] == "known" else "unknown",
                "authority": "explicit" if fact["state"] == "known" else "unknown",
                "supporting_refs": fact["supporting_refs"], "importance": "core",
            } for fact in request["opportunity_facts"]]}})
        return json.dumps({"results": results})


def search_service(repo, client):
    generation_service(repo, Client()).generate("a", "Fixture")
    ingest(job())
    database.ensure_candidate_job_analysis("a", job().id)
    service = object.__new__(CandidateJobAnalysisService)
    service.candidate_repository = CandidateRepository()
    service.career_objective_repository = CareerObjectiveRepository()
    service.career_update_repository = CareerUpdateRepository()
    service.career_memory_repository = CareerMemoryRepository()
    builder = SimpleNamespace(build_job_profile=lambda **kw: JobProfileDraft(needs=(InterpretedJobNeed(
        "need", "Supported capability", RequirementImportance.CORE, InterpretationAuthority.EXPLICIT,
        (kw["hard_facts"].facts[0].fact_id,),
    ),)))
    service.job_profile_manager = JobProfileManager(builder)
    service.ai_service = AIRecommendationService(client)
    service.enricher = SimpleNamespace(enrich=lambda _: pytest.fail("Unexpected enrichment"))
    return service


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.mark.parametrize("unknown", [False, True])
def test_real_search_persists_only_hiring_case_classification(repo, unknown):
    client = RelationshipClient(unknown)
    service = search_service(repo, client)
    result = service.analyze_pending("a", limit=1)
    assert result["failed"] == 0, result["errors"]
    assert client.calls == 1
    with database.get_connection() as connection:
        row = connection.execute("SELECT * FROM candidate_job_analyses WHERE candidate_id = ?", ("a",)).fetchone()
    payload = json.loads(row["analysis_json"])
    assert payload["hiring_case"]["candidate_id"] == "a"
    assert payload["authority"] == "deterministic_hiring_case"
    assert row["current_fit"] is None and row["growth_value"] is None
    assert payload["classification"] == ("not_surfaced" if unknown else "best_match")
    assert row["recommendation"] == ("reject" if unknown else "best_match")
    assert result["ai_approved"] == (0 if unknown else 1)
    if unknown:
        assert row["status"] == "in_review"
        assert row["opportunity_state"] == "none"
        assert result["ai_rejected"] == 0
        assert result["not_surfaced"] == 1


def test_legacy_preference_defaults_cannot_become_hard_incompatibility(repo):
    from dataclasses import replace
    client = RelationshipClient()
    service = search_service(repo, client)
    ingest(replace(job(), description="Night shifts required. Supported capability needed."))
    result = service.analyze_pending("a", limit=1)
    assert result["hard_rejected"] == 0
    assert result["failed"] == 0, result["errors"]
    assert client.calls == 1


def test_closed_vacancy_is_filtered_before_recommendation(repo):
    from dataclasses import replace
    client = RelationshipClient()
    service = search_service(repo, client)
    ingest(replace(job(), description="Applications are closed."))
    result = service.analyze_pending("a", limit=1)
    assert result["hard_rejected"] == 1
    assert client.calls == 0
    with database.get_connection() as connection:
        row = connection.execute("SELECT analysis_json FROM candidate_job_analyses WHERE candidate_id = ?", ("a",)).fetchone()
    assert json.loads(row["analysis_json"])["hiring_case"]["classification"] == "ineligible"


def test_stale_candidate_profile_cannot_trigger_paid_matching(repo):
    client = RelationshipClient()
    service = search_service(repo, client)
    onboarding = repo.get_onboarding("a")
    onboarding.desired_next_work = "Changed explicit direction"
    repo.save_onboarding(onboarding)
    result = service.analyze_pending("a", limit=1)
    assert client.calls == 0
    assert result["failed"] == 1
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM candidate_job_analyses WHERE analysis_claim_token IS NOT NULL").fetchone()[0] == 0
