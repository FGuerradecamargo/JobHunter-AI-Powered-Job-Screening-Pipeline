from dataclasses import replace
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest
import requests

from models.company import CompanyJobSource
from services import database
from services.company_repository import CompanyRepository
from services.company_source_repository import CompanySourceRepository
from services.daily_ingestion_service import DailyIngestionService
from services.employer_provider_factories import employer_provider_factories
from services.employer_provider_registry import build_employer_provider_configs
from services.job_sources.ashby_source import AshbyJobSource
from services.job_sources.lever_source import LeverJobSource
from services.job_sources.board_http import BoardError, BoardHTTPClient
from services.job_sources.provider import JobSourceProvider


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("Live network forbidden in board tests.")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


def source(vendor, board="Acme", identifier="registry1"):
    return CompanyJobSource(identifier, "company1", vendor, board, None, True, "", "")


def posting(vendor, identifier="one", board="Acme"):
    if vendor == "lever":
        return dict(id=identifier, text="Engineer", categories={"location": "Dublin"},
                    hostedUrl=f"https://jobs.lever.co/{board}/{identifier}",
                    descriptionPlain="Build tools", workplaceType="remote")
    return dict(title="Engineer", location="Dublin", isListed=True, isRemote=True,
                jobUrl=f"https://jobs.ashbyhq.com/{board}/{identifier}",
                descriptionPlain="Build tools", publishedAt="2026-09-01T12:00:00Z")


def payload(vendor, records):
    return records if vendor == "lever" else {"apiVersion": "1", "jobs": records}


class FakeHTTP:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, *, params):
        self.calls.append((url, params))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


ADAPTERS = {"lever": LeverJobSource, "ashby": AshbyJobSource}


@pytest.mark.parametrize("vendor", ADAPTERS)
def test_board_multiple_stable_normalized_jobs(vendor):
    data = payload(vendor, [posting(vendor), posting(vendor, "two")])
    http = FakeHTTP(data, data)
    adapter = ADAPTERS[vendor](source(vendor), "Acme Inc", http)
    first, second = adapter.search(), adapter.search()
    assert isinstance(adapter, JobSourceProvider)
    assert [j.id for j in first] == [j.id for j in second]
    assert first[0].id == f"{vendor}:registry1:Acme:one"
    assert first[0].company == "Acme Inc"
    assert first[0].location == "Dublin"
    assert first[0].remote is True
    assert first[0].description == "Build tools"
    assert "Build tools" in first[0].raw_text
    assert first[0].easy_apply is False


@pytest.mark.parametrize("vendor", ADAPTERS)
def test_malformed_posting_does_not_abort_board(vendor):
    http = FakeHTTP(payload(vendor, [None, {}, {"title": []}, posting(vendor)]))
    adapter = ADAPTERS[vendor](source(vendor), "Acme", http)
    assert len(adapter.search()) == 1
    assert adapter.skipped_records == 3


@pytest.mark.parametrize("vendor", ADAPTERS)
def test_missing_optional_fields_preserves_unknowns(vendor):
    record = posting(vendor)
    for field in ("location", "categories", "descriptionPlain", "workplaceType", "isRemote", "publishedAt"):
        record.pop(field, None)
    job = ADAPTERS[vendor](source(vendor), "Acme", FakeHTTP(payload(vendor, [record]))).search()[0]
    assert job.location is job.remote is job.description is job.published_at is None
    assert job.title == "Engineer"


@pytest.mark.parametrize("vendor", ADAPTERS)
@pytest.mark.parametrize("url", ["http://127.0.0.1/private", "https://169.254.169.254/meta",
    "file:///tmp/jobs", "javascript:alert(1)", "https://jobs.lever.co.evil.test/Acme/one",
    "https://user:password@jobs.lever.co/Acme/one", "https://jobs.ashbyhq.com:443/Acme/one",
    "https://jobs.ashbyhq.com/Other/one", "https://jobs.lever.co/Acme/../private"])
def test_invalid_posting_urls_are_skipped(vendor, url):
    record = posting(vendor)
    record["hostedUrl" if vendor == "lever" else "jobUrl"] = url
    adapter = ADAPTERS[vendor](source(vendor), "Acme", FakeHTTP(payload(vendor, [record])))
    assert adapter.search() == []
    assert adapter.skipped_records == 1


@pytest.mark.parametrize("vendor", ADAPTERS)
@pytest.mark.parametrize("key", ["https://evil.test", "../foo", "%2fetc", "a?host=evil",
                                   "a#b", "user@host", "a\\b", "127.0.0.1", ""])
def test_board_key_cannot_inject_host_or_path(vendor, key):
    http = FakeHTTP()
    with pytest.raises(BoardError, match="invalid_source_key"):
        ADAPTERS[vendor](source(vendor, key), "Acme", http)
    assert not http.calls


def test_lever_all_pages_and_description_sections():
    first = posting("lever")
    first.pop("descriptionPlain")
    first.update(description="<p>Build &amp; learn</p><script>secret()</script>",
                 lists=[{"text": "Requirements", "content": "<li>SQL</li>"}],
                 additionalPlain="Welcome", workplaceType="hybrid")
    http = FakeHTTP([first], [posting("lever", "two")], [])
    adapter = LeverJobSource(source("lever"), "Acme", http)
    jobs = adapter.search(results_per_page=1)
    assert len(jobs) == 2
    assert [p[1]["skip"] for p in http.calls] == [0, 1, 2]
    assert jobs[0].description == "Build & learn\nRequirements\nSQL\nWelcome"
    assert jobs[0].remote is None


def test_lever_eu_template_and_private_registry_url_not_used_as_endpoint():
    row = replace(source("lever"), careers_url="https://jobs.eu.lever.co/Acme")
    record = posting("lever")
    record["hostedUrl"] = "https://jobs.eu.lever.co/Acme/one"
    http = FakeHTTP([record])
    assert len(LeverJobSource(row, "Acme", http).search()) == 1
    assert http.calls[0][0] == "https://api.eu.lever.co/v0/postings/Acme"
    other = replace(row, careers_url="http://127.0.0.1/secret")
    assert LeverJobSource(other, "Acme").endpoint == "https://api.lever.co/v0/postings/Acme"


@pytest.mark.parametrize("stalled", [False, True])
def test_lever_never_returns_truncated_board_as_complete(stalled):
    record = posting("lever")
    http = FakeHTTP([record], [record])
    adapter = LeverJobSource(source("lever"), "Acme", http)
    adapter.MAX_PAGES = 2 if stalled else 1
    with pytest.raises(BoardError, match="pagination_stalled" if stalled else "pagination_limit"):
        adapter.search(results_per_page=1)


def test_ashby_url_identity_date_and_unlisted_filter():
    record = posting("ashby")
    record["secondaryLocations"] = [{"location": "London"}, {"location": "Dublin"}]
    other = dict(record, id="new-undocumented-field")
    http = FakeHTTP(payload("ashby", [record, dict(record, isListed=False)]), payload("ashby", [other]))
    adapter = AshbyJobSource(source("ashby"), "Acme", http)
    job = adapter.search(results_per_page=1)[0]
    assert adapter.skipped_records == 1
    assert job.published_at == datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    assert job.location == "Dublin; London"
    assert adapter.search()[0].id == job.id
    assert len(http.calls) == 2  # One request per full-board read, no pagination.


@pytest.mark.parametrize("value", ["bad", "2026-01-01", 123, None])
def test_bad_or_naive_published_date_is_not_invented(value):
    record = dict(posting("ashby"), publishedAt=value)
    job = AshbyJobSource(source("ashby"), "Acme", FakeHTTP(payload("ashby", [record]))).search()[0]
    assert job.published_at is None


@pytest.mark.parametrize("vendor", ADAPTERS)
@pytest.mark.parametrize("data", [None, "html", {}, {"jobs": "bad"}, 42])
def test_response_shape_error(vendor, data):
    with pytest.raises(BoardError, match="response_shape"):
        ADAPTERS[vendor](source(vendor), "Acme", FakeHTTP(data)).search()


class Response:
    def __init__(self, value=None, status=200, headers=None, raw=None):
        self.status_code = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.raw = raw if raw is not None else json.dumps(value).encode()
        self.closed = False
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.closed = True
    def iter_content(self, chunk_size):
        yield self.raw


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.trust_env = True
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.mark.parametrize("vendor", ADAPTERS)
@pytest.mark.parametrize("failure", [requests.Timeout("secret"), Response(status=403), Response(raw=b"not json")])
def test_http_error_timeout_and_invalid_json(vendor, failure):
    session = Session(failure, failure, failure)
    sleeps = []
    client = BoardHTTPClient(lambda: session, sleeps.append)
    with pytest.raises(BoardError) as error:
        ADAPTERS[vendor](source(vendor), "Acme", client).search()
    assert "secret" not in str(error.value)
    assert len(session.calls) == (3 if isinstance(failure, requests.Timeout) else 1)
    assert len(sleeps) <= 2
    assert not session.trust_env
    assert all(c[1]["timeout"] == (5, 20) and c[1]["allow_redirects"] is False for c in session.calls)


@pytest.mark.parametrize("endpoint", ["http://api.lever.co/v0/postings/Acme", "https://evil.test/jobs",
    "https://api.lever.co@127.0.0.1/v0/postings/Acme", "https://api.ashbyhq.com/posting-api/job-board/../x",
    "https://api.lever.co/v0/postings/Acme?redirect=evil", "https://api.lever.co:443/v0/postings/Acme"])
def test_http_boundary_rejects_non_allowlisted_endpoint(endpoint):
    session = Session()
    with pytest.raises(BoardError, match="invalid_endpoint"):
        BoardHTTPClient(lambda: session).get_json(endpoint, params={})
    assert session.calls == []


@pytest.mark.parametrize("response,code", [(Response(status=302, headers={"Location": "http://127.0.0.1"}), "http_status"),
    (Response(headers={"Content-Type": "text/html"}), "content_type"),
    (Response(status=429, headers={"Retry-After": "120"}), "rate_limited")])
def test_redirect_content_type_and_long_retry_fail_safely(response, code):
    session = Session(response)
    with pytest.raises(BoardError, match=code):
        BoardHTTPClient(lambda: session).get_json("https://api.lever.co/v0/postings/Acme", params={})
    assert response.closed
    assert len(session.calls) == 1


def test_bounded_response_and_retry_recovery():
    session = Session(Response(status=503), Response(value=[]))
    waits = []
    assert BoardHTTPClient(lambda: session, waits.append).get_json(
        "https://api.lever.co/v0/postings/Acme", params={}) == []
    assert waits == [0.5]
    response = Response(raw=b"a" * 11)
    client = BoardHTTPClient(lambda: Session(response))
    client.MAX_BYTES = 10
    with pytest.raises(BoardError, match="response_too_large"):
        client.get_json("https://api.lever.co/v0/postings/Acme", params={})
    assert response.closed


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(database, "DATABASE_FILE", tmp_path / "boards.db")
    database.initialize_database.cache_clear()
    database.initialize_database()
    yield
    database.initialize_database.cache_clear()


def test_registry_ingestion_provenance_freshness_and_no_private_metadata(db):
    company = CompanyRepository().get_or_create_company("Acme Inc")
    repo = CompanySourceRepository()
    rows = [repo.upsert_company_source(company.id, vendor, "Acme") for vendor in ADAPTERS]
    rows += [replace(rows[0], enabled=False, id="disabled"), replace(rows[0], source_type="unknown")]
    class HTTP:
        def get_json(self, url, *, params):
            vendor = "lever" if "lever.co" in url else "ashby"
            record = dict(posting(vendor), candidate_id="PRIVATE", watchlist="PRIVATE")
            return payload(vendor, [record])
    configs = build_employer_provider_configs(rows, employer_provider_factories(http_factory=HTTP))
    assert len(configs) == 2
    result = DailyIngestionService(providers=configs).run(0)
    assert result.totals["created"] == 2
    with database.get_connection() as conn:
        conn.execute("UPDATE job_sources SET last_seen_at = '2000-01-01'")
    second = DailyIngestionService(providers=configs).run(1)
    assert second.totals["created"] == 0
    with database.get_connection() as conn:
        jobs = [dict(r) for r in conn.execute("SELECT * FROM jobs").fetchall()]
        sources = [dict(r) for r in conn.execute("SELECT * FROM job_sources").fetchall()]
    assert len(jobs) == 2
    assert all(j["company"] == "Acme Inc" and j["archived_at"] is None for j in jobs)
    assert "PRIVATE" not in repr(jobs) + repr(sources)
    assert all(s["user_id"] is None and s["last_seen_at"] != "2000-01-01" for s in sources)
    assert {s["source_type"] for s in sources} == {c.source_type for c in configs}


def test_multiple_boards_and_provider_failure_do_not_abort_others(db):
    company = CompanyRepository().get_or_create_company("Acme")
    rows = [replace(source("lever", board, board), company_id=company.id) for board in ["Broken", "Good"]]
    rows.append(replace(source("ashby"), company_id=company.id))
    class HTTP:
        def get_json(self, url, *, params):
            if url.endswith("Broken"):
                raise BoardError("http_status")
            vendor = "lever" if "lever.co" in url else "ashby"
            return payload(vendor, [posting(vendor, board=url.rsplit("/", 1)[-1])])
    configs = build_employer_provider_configs(rows, employer_provider_factories(http_factory=HTTP))
    result = DailyIngestionService(providers=configs).run(0)
    assert result.providers["lever:Broken"].status == "failed"
    assert result.totals["created"] == 2


def test_setup_failure_is_distinct_and_factories_are_lazy():
    calls = []
    repo = SimpleNamespace(get=lambda key: calls.append(key))
    configs = build_employer_provider_configs([source("lever")], employer_provider_factories(repo))
    assert not calls
    result = DailyIngestionService(providers=configs).run(0)
    assert result.providers["lever:registry1"].error_code == "provider_setup_failed"
    assert calls == ["company1"]


def test_ashby_returns_entire_board_despite_query_result_hint():
    data = payload("ashby", [posting("ashby", str(i)) for i in range(3)])
    adapter = AshbyJobSource(source("ashby"), "Acme", FakeHTTP(data))
    assert len(adapter.search(results_per_page=1)) == 3


@pytest.mark.parametrize("vendor", ADAPTERS)
def test_resource_caps_fail_not_silently_truncate(vendor):
    adapter = ADAPTERS[vendor](source(vendor), "Acme", FakeHTTP(payload(vendor, [posting(vendor)])))
    adapter.MAX_JOBS = 0
    with pytest.raises(BoardError, match="board_too_large"):
        adapter.search()


@pytest.mark.parametrize("vendor", ADAPTERS)
def test_no_candidate_queries_sent_to_employer(vendor):
    http = FakeHTTP()
    with pytest.raises(BoardError, match="unsupported_search"):
        ADAPTERS[vendor](source(vendor), "Acme", http).search(keywords="PRIVATE")
    assert not http.calls


def test_finite_rate_limit_retries():
    session = Session(*[Response(status=429, headers={"Retry-After": "2"}) for _ in range(3)])
    waits = []
    with pytest.raises(BoardError, match="http_retry_exhausted"):
        BoardHTTPClient(lambda: session, waits.append).get_json(
            "https://api.ashbyhq.com/posting-api/job-board/Acme", params={})
    assert len(session.calls) == 3
    assert waits == [2, 2]


def test_lever_description_fallback_and_identity_mismatch():
    record = posting("lever")
    record.pop("descriptionPlain")
    record.update(openingPlain="Opening", descriptionBody="<p>Body</p>")
    adapter = LeverJobSource(source("lever"), "Acme", FakeHTTP([record, dict(record, id="different")]))
    assert adapter.search()[0].description == "Opening\nBody"
    assert adapter.skipped_records == 1


def test_empty_later_board_does_not_close_existing_jobs(db):
    company = CompanyRepository().get_or_create_company("Acme")
    row = replace(source("ashby"), company_id=company.id)
    http = FakeHTTP(payload("ashby", [posting("ashby")]), payload("ashby", []))
    configs = build_employer_provider_configs([row], employer_provider_factories(http_factory=lambda: http))
    DailyIngestionService(providers=configs).run(0)
    result = DailyIngestionService(providers=configs).run(1)
    assert result.totals["fetched"] == 0
    with database.get_connection() as conn:
        jobs = conn.execute("SELECT archived_at FROM jobs").fetchall()
    assert len(jobs) == 1 and jobs[0]["archived_at"] is None


def test_later_page_failure_does_not_persist_incomplete_board(db):
    company = CompanyRepository().get_or_create_company("Acme")
    row = replace(source("lever"), company_id=company.id)
    http = FakeHTTP([posting("lever", str(i)) for i in range(20)], BoardError("http_status"))
    configs = build_employer_provider_configs([row], employer_provider_factories(http_factory=lambda: http))
    result = DailyIngestionService(providers=configs).run(0)
    assert result.providers["lever:registry1"].status == "failed"
    assert result.totals["created"] == 0
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


@pytest.mark.parametrize("hint", ["9" * 5000, "\u00b2"])
def test_malformed_retry_hint_is_sanitized(hint):
    session = Session(Response(status=429, headers={"Retry-After": hint}))
    with pytest.raises(BoardError, match="rate_limited"):
        BoardHTTPClient(lambda: session).get_json("https://api.lever.co/v0/postings/Acme", params={})


def test_malformed_html_isolated_from_valid_sibling():
    bad = posting("lever")
    bad.pop("descriptionPlain")
    bad["description"] = "<![bogus[>"
    adapter = LeverJobSource(source("lever"), "Acme", FakeHTTP([bad, posting("lever", "two")]))
    assert [job.id for job in adapter.search()] == ["lever:registry1:Acme:two"]
    assert adapter.skipped_records == 1
