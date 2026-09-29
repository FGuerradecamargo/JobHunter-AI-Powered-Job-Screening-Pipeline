"""Real preparation/claims/persistence with fake profile and recommendation AI."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from models.job_profile import JobProfile
from models.profile_interpretation import JobProfileDraft, JobHardFacts
from services import database
from services.job_profile_manager import JobProfileManager
from services.job_search_repository import JobSearchRepository
from services.opportunity_search_run import OpportunitySearchRun
import services.candidate_job_analysis_service as analysis_module
from tests.test_candidate_job_analysis_trace_wiring import _build_service, FakeAIResult
from tests.test_source_v2_foundation import db, discovery_pool, no_network
from tests.test_opportunity_search_cancellation import page_unit


@pytest.fixture
def search(monkeypatch, discovery_pool, page_unit):
    service = _build_service(monkeypatch)
    service.candidate_repository = SimpleNamespace(get=lambda cid: object())
    service.career_objective_repository = SimpleNamespace(get_active=lambda cid: None)
    service.career_update_repository = SimpleNamespace(list_for_candidate=lambda cid: [])
    service.career_memory_repository = SimpleNamespace(get_snapshot=lambda cid: None)
    service.enricher = SimpleNamespace(enrich=lambda job: setattr(job, "description", "Fixture"))
    profile_ai = Mock()
    profile_ai.build_job_profile.side_effect = lambda **kw: JobProfileDraft(needs=())
    service.job_profile_manager = JobProfileManager(profile_ai, source_repository=SimpleNamespace(
        load_job_hard_facts=lambda job_id, **kw: JobHardFacts(job_id, job_id, ())))
    rejected = set()
    service._prepare_hiring_case = lambda cid, job: {
        "rejected": job.id in rejected, "reasons": ["Fixture constraint"],
    }
    monkeypatch.setattr(analysis_module, "HardFilterAnalyzer", lambda profile: SimpleNamespace(
        analyze=lambda job, jp: {"rejected": job.id in rejected, "reasons": ["Fixture constraint"]},
    ))
    ai = Mock()
    ai.analyze_hiring_cases_batch.side_effect = lambda requests: [FakeAIResult(req.job_id, req.candidate_id) for req in requests]
    service.ai_service = ai
    env = page_unit
    env.update(candidate_id="a", repository=JobSearchRepository(), analysis_service=service,
               ensure_candidate_job_analysis=database.ensure_candidate_job_analysis)
    # Exercise the production activation helper as well as the unit.
    source = (Path(__file__).resolve().parents[1] / "pages/1_Opportunities.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                and n.name == "activate_ready_opportunities")
    env.update(list_inactive_approved_candidate_jobs=database.list_inactive_approved_candidate_jobs,
               activate_candidate_opportunities=database.activate_candidate_opportunities)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "activation", "exec"), env)
    run = OpportunitySearchRun("actor", "owner", "a", "sig", 5, env["empty_scan_result"]())
    run.initialized = True
    env["search_run"] = run

    def add(count, rejects=()):
        for index in range(count):
            identifier = f"job-{index:02}"
            discovery_pool(identifier, identifier)
        rejected.update(f"job-{index:02}" for index in rejects)

    def step():
        current = env["search_run"]
        current.advance(current.scope, env["advance_opportunity_search"])
        with database.get_connection() as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM candidate_job_analyses "
                "WHERE COALESCE(analysis_claim_token, '') <> ''",
            ).fetchone()[0] == 0
        assert len(current.prepared_job_ids) <= 10
        assert current.status != "failed", current.aggregate["errors"]

    return SimpleNamespace(env=env, run=run, add=add, step=step, ai=ai,
                           service=service, profile_ai=profile_ai, rejected=rejected)


def test_ten_inspected_seven_survivors_wait_then_send_ten(search):
    search.add(15, rejects=(14, 13, 12, 4, 3))
    for _ in range(10):
        search.step()
    assert search.run.aggregate["selected"] == 10
    assert search.run.aggregate["hard_rejected"] == 3
    assert len(search.run.prepared_job_ids) == 7
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    for _ in range(5):
        search.step()
    assert len(search.run.prepared_job_ids) == 10
    assert not search.rejected.intersection(search.run.prepared_job_ids)
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    search.step()
    search.ai.analyze_hiring_cases_batch.assert_called_once()
    assert len(search.ai.analyze_hiring_cases_batch.call_args.args[0]) == 10
    assert not search.run.prepared_job_ids
    assert search.run.unavailable_job_ids == set()
    assert search.run.aggregate["selected"] == 15
    assert search.run.aggregate["analyzed"] == 15
    assert search.profile_ai.build_job_profile.call_count == 15  # Reload uses the persisted cache.


def test_exhausted_pool_flushes_six_once(search):
    search.add(6)
    for _ in range(6):
        search.step()
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    search.step()
    assert len(search.ai.analyze_hiring_cases_batch.call_args.args[0]) == 6
    search.step()
    assert search.run.status == "complete"
    search.ai.analyze_hiring_cases_batch.assert_called_once()


def test_stop_keeps_preparation_without_paid_flush_and_new_search_reuses_it(search):
    search.add(6)
    for _ in range(6):
        search.step()
    search.run.stop(search.run.scope, search.run.scan_id)
    search.step()
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    search.env["search_run"] = OpportunitySearchRun(
        *search.run.scope, target=5, aggregate=search.env["empty_scan_result"](), initialized=True,
    )
    for _ in range(7):
        search.step()
    search.ai.analyze_hiring_cases_batch.assert_called_once()
    assert search.profile_ai.build_job_profile.call_count == 6


def test_partial_claim_race_refills_before_recommendation(search, monkeypatch):
    search.add(12)
    for _ in range(10):
        search.step()
    original = analysis_module.list_pending_candidate_jobs
    lost = set(search.run.prepared_job_ids[:2])
    raced = False
    def partial(**kwargs):
        nonlocal raced
        if not raced and kwargs["limit"] == 10:
            raced = True
            kwargs["job_ids"] = [j for j in kwargs["job_ids"] if j not in lost]
        return original(**kwargs)
    monkeypatch.setattr(analysis_module, "list_pending_candidate_jobs", partial)
    search.step()
    assert len(search.run.prepared_job_ids) == 8
    assert search.run.unavailable_job_ids == lost
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    for _ in range(3):
        search.step()
    search.ai.analyze_hiring_cases_batch.assert_called_once()
    assert len(search.ai.analyze_hiring_cases_batch.call_args.args[0]) == 10
    assert search.run.unavailable_job_ids == lost


def test_revalidation_hard_reject_is_removed_before_refill(search):
    search.add(11)
    for _ in range(10):
        search.step()
    rejected_id = search.run.prepared_job_ids[0]
    search.rejected.add(rejected_id)
    search.step()
    assert len(search.run.prepared_job_ids) == 9
    assert search.run.unavailable_job_ids == set()
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    search.step()
    search.step()
    assert len(search.ai.analyze_hiring_cases_batch.call_args.args[0]) == 10
    assert rejected_id not in {req.job_id for req in search.ai.analyze_hiring_cases_batch.call_args.args[0]}
    assert search.run.unavailable_job_ids == set()


def test_target_five_activates_only_five_after_ten_eligible(search, monkeypatch):
    search.add(12)
    from dataclasses import replace
    from services.ai.ai_recommendation_service import AIRecommendationService
    from services.hiring_case_compatibility import hiring_case_analysis
    from tests.test_v1_runtime_hiring_case_batch import Client, inputs, response
    req = inputs()[0]
    case = AIRecommendationService(Client([response(req)])).analyze_hiring_cases_batch([req])[0]
    monkeypatch.setattr(analysis_module, "hiring_case_analysis", lambda result: hiring_case_analysis(
        replace(case, candidate_id=result.candidate_id, job_id=result.job_id)))
    for _ in range(11):
        search.step()
    assert search.run.status == "complete"
    assert search.run.aggregate["opportunities_found"] == 5
    search.ai.analyze_hiring_cases_batch.assert_called_once()
    assert len(search.ai.analyze_hiring_cases_batch.call_args.args[0]) == 10
    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_job_analyses WHERE candidate_id='a' AND opportunity_state='active'",
        ).fetchone()[0] == 5


def test_preparation_exception_releases_claim_and_stops_without_ai(search):
    search.add(1)
    search.profile_ai.build_job_profile.side_effect = RuntimeError("fixture")
    search.run.advance(search.run.scope, search.env["advance_opportunity_search"])
    assert search.run.status == "failed"
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_job_analyses WHERE analysis_claim_token IS NOT NULL",
        ).fetchone()[0] == 0


def test_active_buffer_claims_are_not_stolen_or_held_while_refilling(search):
    search.add(12)
    for _ in range(10):
        search.step()
    busy = search.run.prepared_job_ids[:2]
    claimed = database.list_pending_candidate_jobs(
        "a", limit=2, job_ids=busy, claim_token="other-worker", claim_ttl_seconds=1800,
    )
    assert len(claimed) == 2
    search.run.advance(search.run.scope, search.env["advance_opportunity_search"])
    assert len(search.run.prepared_job_ids) == 8
    search.ai.analyze_hiring_cases_batch.assert_not_called()
    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_job_analyses WHERE analysis_claim_token = 'other-worker'",
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_job_analyses WHERE analysis_claim_token IS NOT NULL",
        ).fetchone()[0] == 2
    database.release_candidate_job_analysis_claims(candidate_id="a", job_ids=busy, claim_token="other-worker")
    for _ in range(3):
        search.step()
    search.ai.analyze_hiring_cases_batch.assert_called_once()
    assert len(search.ai.analyze_hiring_cases_batch.call_args.args[0]) == 10


def test_full_buffer_insufficient_budget_stops_without_partial_paid_batch(search):
    from services.ai_usage_budget import AIUsageBudget
    search.add(11)
    search.run.budget = AIUsageBudget(remaining=5)
    for _ in range(11):
        search.step()
    assert search.run.status == "complete"
    assert search.run.aggregate["usage_limit_reached"]
    search.ai.analyze_hiring_cases_batch.assert_not_called()


def test_recommendation_quota_failure_stops_once_and_releases_claims(search):
    from services.provider_failure import ProviderRateLimit
    search.add(10)
    search.ai.analyze_hiring_cases_batch.side_effect = ProviderRateLimit()
    for _ in range(10):
        search.step()
    search.run.advance(search.run.scope, search.env["advance_opportunity_search"])
    assert search.run.status == "failed"
    assert search.run.aggregate["provider_quota_exhausted"]
    search.run.advance(search.run.scope, search.env["advance_opportunity_search"])
    search.ai.analyze_hiring_cases_batch.assert_called_once()
    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_job_analyses WHERE analysis_claim_token IS NOT NULL",
        ).fetchone()[0] == 0
