from dataclasses import replace
import json
import logging
import socket

import pytest

from models.hiring_case import HiringCaseClassification as Classification
from models.hiring_case import OpportunitySignalKind as Kind
from models.structured_interpretation import FactState, OpportunityFact, SourceRefClass
from services.ai.ai_recommendation_service import AIRecommendationService
from tests.test_offline_structured_interpreter import request, link


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


class Client:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        assert "Never classify, score, recommend" in prompt
        return json.dumps({"results": self.rows})


def inputs(count=1):
    base = request()
    base = replace(base, opportunity_facts=(OpportunityFact(
        Kind.CAREER_DIRECTION, FactState.KNOWN, ("memory:context", "f1"),
        ("Candidate explicitly seeks support work; the public vacancy requires support work.",),
    ),))
    return [replace(base, job_id=f"job-{i}",
        job_profile=replace(base.job_profile, job_id=f"job-{i}"),
        hard_facts=replace(base.hard_facts, job_id=f"job-{i}"),
        source_registry=tuple(replace(ref, owner_id=f"job-{i}")
            if ref.source_class is SourceRefClass.JOB_HARD_FACT else ref for ref in base.source_registry),
    ) for i in range(count)]


def response(req, *, semantic=None):
    return {"job_id": req.job_id, "semantic": semantic if semantic is not None else link(),
            "opportunity": {"signals": [{"kind": "career_direction", "factual_state": "known",
                "state": "positive", "authority": "explicit", "supporting_refs": ["memory:context", "f1"],
                "importance": "core"}]}}


def test_one_batch_of_ten_returns_engine_cases_in_requested_order():
    requests = inputs(10)
    client = Client([response(req) for req in reversed(requests)])
    cases = AIRecommendationService(client).analyze_hiring_cases_batch(requests)
    assert client.calls == 1
    assert [case.job_id for case in cases] == [req.job_id for req in requests]
    assert all(case.classification is Classification.BEST_MATCH for case in cases)


def test_zero_evaluated_requirements_never_surfaces_even_with_positive_value():
    req = inputs()[0]
    unknown = link(candidate_capability_id=None, assessment="evidence_missing", evidence_refs=[],
                   confidence="unknown", reason_code="uncertain", needs_evidence=True)
    case = AIRecommendationService(Client([response(req, semantic=unknown)])).analyze_hiring_cases_batch([req])[0]
    assert case.classification is Classification.NOT_SURFACED
    assert case.evaluated_requirement_count == 0


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "extra", "unknown_ref", "model_bucket"])
def test_batch_rejects_atomically_without_retry(corruption):
    requests = inputs(2)
    rows = [response(req) for req in requests]
    if corruption == "missing":
        rows.pop()
    elif corruption == "duplicate":
        rows[1]["job_id"] = rows[0]["job_id"]
    elif corruption == "extra":
        rows.append(response(inputs(3)[2]))
    elif corruption == "unknown_ref":
        rows[1]["semantic"] = link(evidence_refs=["private-unrelated-ref"])
    else:
        rows[1]["recommendation"] = "best_match"
    client = Client(rows)
    with pytest.raises(ValueError):
        AIRecommendationService(client).analyze_hiring_cases_batch(requests)
    assert client.calls == 1


@pytest.mark.parametrize("count", [0, 11])
def test_invalid_batch_size_never_calls_provider(count):
    client = Client([])
    with pytest.raises(ValueError):
        AIRecommendationService(client).analyze_hiring_cases_batch(inputs(count))
    assert client.calls == 0


def test_cross_candidate_scope_is_rejected_before_provider():
    requests = inputs(2)
    requests[1] = replace(requests[1], candidate_profile=replace(requests[1].candidate_profile, candidate_id="another"))
    client = Client([])
    with pytest.raises(ValueError):
        AIRecommendationService(client).analyze_hiring_cases_batch(requests)
    assert client.calls == 0


def test_unknown_candidate_value_cannot_be_promoted_and_logs_are_sanitized(caplog):
    req = inputs()[0]
    req = replace(req, opportunity_facts=(OpportunityFact(Kind.CAREER_DIRECTION, FactState.UNKNOWN),))
    row = response(req)
    row["opportunity"]["signals"][0]["supporting_refs"] = []
    row["opportunity"]["signals"][0]["uncertainty"] = "PRIVATE GENERATED CONTENT"
    with caplog.at_level(logging.INFO):
        case = AIRecommendationService(Client([row])).analyze_hiring_cases_batch([req])[0]
    assert case.classification is not Classification.BEST_MATCH
    assert "PRIVATE GENERATED CONTENT" not in caplog.text
    assert "unknown_opportunity_fact" in caplog.text
