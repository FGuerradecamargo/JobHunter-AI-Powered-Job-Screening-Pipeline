import pytest
import requests

from models.job import Job
from scripts.validate_launch_coverage import PROFILES, RequestBudget, assess
from services.job_sources.board_http import BoardError


def job(location="Dublin", remote=False, text="Customer support"):
    return Job(id="fixture", raw_text=text, url="https://example.test/job",
               title="Customer Support", location=location, remote=remote)


def test_ten_distinct_synthetic_profiles():
    assert len(PROFILES) == len({p.name for p in PROFILES}) == 10
    assert {p.market for p in PROFILES} == {"IE", "UK", "EU"}
    assert any(p.remote_only for p in PROFILES)


def test_location_and_mode_are_not_inferred_from_remote_alone():
    result = assess([job("New York", True), job("London", None), job("London", True)], PROFILES[7])
    assert result["title_plausible"] == 3
    assert result["plausible_location_mode"] == 1
    assert result["deterministic_survivors"] == 1
    assert result["human_attention_verified"] is None


def test_existing_hard_filter_rejects_closed_posting():
    result = assess([job(text="Applications are closed")], PROFILES[0])
    assert result["plausible_location_mode"] == 1
    assert result["deterministic_survivors"] == 0
    assert result["assessment"] == "insufficient"


def test_budget_counts_actual_send_and_never_exceeds_limit(monkeypatch):
    sent = []
    monkeypatch.setattr(requests.Session, "send", lambda self, request, **kw: sent.append(request.url))
    budget = RequestBudget(limit=1)
    request = requests.Request("GET", "https://api.lever.co/v0/postings/zopa").prepare()
    with budget.session() as session:
        session.send(request)
        with pytest.raises(BoardError):
            session.send(request)
    assert budget.calls == len(sent) == 1


@pytest.mark.parametrize("method,url", [("POST", "https://api.lever.co/v0/postings/zopa"),
                                       ("GET", "https://api.openai.com/v1/models")])
def test_budget_rejects_other_calls(method, url):
    budget = RequestBudget()
    with budget.session() as session, pytest.raises(RuntimeError, match="Unapproved"):
        session.send(requests.Request(method, url).prepare())
    assert budget.calls == 0
