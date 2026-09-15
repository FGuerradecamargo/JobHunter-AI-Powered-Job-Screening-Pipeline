import json
from types import SimpleNamespace

import pytest

from scripts.validate_aggregator_coverage import SafeHTTP, safe_output, collect, PLAN
from services.job_sources.board_http import BoardError


class Session:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def request(self, method, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        assert self.trust_env is False
        return Response()


class Response(Session):
    status_code = 200
    def iter_content(self, size):
        yield b'{"results": [], "jobs": []}'


@pytest.mark.parametrize("vendor,url", [("adzuna", "https://api.adzuna.com/test"), ("jooble", "https://jooble.org/api/fake")])
def test_request_budget_includes_repeat_calls(vendor, url):
    http = SafeHTTP(vendor, Session)
    for _ in range(12):
        http.request(url)
    with pytest.raises(BoardError):
        http.request(url)
    assert http.attempts == http.successes == 12


def test_raw_exception_not_exposed():
    class Failed(Session):
        def request(self, *args, **kw):
            raise RuntimeError("SECRET-CREDENTIAL-URL")
    with pytest.raises(BoardError) as error:
        SafeHTTP("jooble", Failed).request("https://jooble.org/api/fake")
    assert "SECRET" not in str(error.value)
    assert error.value.__suppress_context__


def test_unapproved_host_never_requested():
    http = SafeHTTP("adzuna", Session)
    with pytest.raises(BoardError):
        http.request("https://example.test/")
    assert http.attempts == 0


def test_evidence_removes_urls_and_encoded_secrets():
    result = safe_output({"url":"anything", "text":"abc/def abc%2Fdef", "nested":[{"url":"hidden"}]}, ["abc/def"])
    assert "url" not in json.dumps(result)
    assert "abc" not in json.dumps(result)


@pytest.mark.parametrize("vendor", ["adzuna", "jooble"])
def test_collect_uses_actual_adapter_with_fake_transport(monkeypatch, vendor):
    from services.job_sources import adzuna_source, jooble_source
    for module in (adzuna_source, jooble_source):
        monkeypatch.setattr(module, "load_dotenv", lambda: None)
    for key in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JOOBLE_API_KEY"):
        monkeypatch.setenv(key, "fake")
    jobs, metric = collect(vendor, "ie", "support", SafeHTTP(vendor, Session))
    assert jobs == []
    assert metric["requests"] == 1
    assert metric["error_code"] is None
    assert metric["coverage_complete"] is False


def test_plan_reserves_capacity_and_has_both_markets():
    assert len(PLAN) + 2 <= 12
    assert {m for m, q in PLAN} == {"ie", "gb"}
