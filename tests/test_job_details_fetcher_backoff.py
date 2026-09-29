from pathlib import Path

import requests

import services.job_details_fetcher as fetcher


HTML = """
<html>
  <div class="show-more-less-html__markup">
    Fixture job description
  </div>
</html>
"""


class Response:
    def __init__(
        self,
        status_code,
        *,
        text="",
        headers=None,
    ):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def raise_for_status(
        self,
    ):
        if self.status_code < 400:
            return

        response = requests.Response()
        response.status_code = (
            self.status_code
        )
        response.url = (
            "https://example.invalid/job"
        )

        raise requests.HTTPError(
            response=response
        )


def test_successful_fetch_has_no_artificial_sleep(
    monkeypatch,
):
    sleeps = []

    monkeypatch.setattr(
        fetcher.requests,
        "get",
        lambda *args, **kwargs: Response(
            200,
            text=HTML,
        ),
    )

    monkeypatch.setattr(
        fetcher.time,
        "sleep",
        sleeps.append,
    )

    result = (
        fetcher.fetch_job_description(
            "https://example.invalid/job"
        )
    )

    assert (
        result
        == "Fixture job description"
    )

    assert sleeps == []


def test_rate_limit_uses_one_bounded_retry(
    monkeypatch,
):
    responses = iter(
        (
            Response(
                429,
                headers={
                    "Retry-After": "1"
                },
            ),
            Response(
                200,
                text=HTML,
            ),
        )
    )

    sleeps = []
    calls = []

    def get(
        *args,
        **kwargs,
    ):
        calls.append(
            True
        )

        return next(
            responses
        )

    monkeypatch.setattr(
        fetcher.requests,
        "get",
        get,
    )

    monkeypatch.setattr(
        fetcher.time,
        "sleep",
        sleeps.append,
    )

    result = (
        fetcher.fetch_job_description(
            "https://example.invalid/job"
        )
    )

    assert (
        result
        == "Fixture job description"
    )

    assert len(
        calls
    ) == 2

    assert sleeps == [
        1.0
    ]


def test_long_retry_after_does_not_block_runtime(
    monkeypatch,
):
    sleeps = []
    calls = []

    def get(
        *args,
        **kwargs,
    ):
        calls.append(
            True
        )

        return Response(
            429,
            headers={
                "Retry-After": "30"
            },
        )

    monkeypatch.setattr(
        fetcher.requests,
        "get",
        get,
    )

    monkeypatch.setattr(
        fetcher.time,
        "sleep",
        sleeps.append,
    )

    assert (
        fetcher.fetch_job_description(
            "https://example.invalid/job"
        )
        is None
    )

    assert len(
        calls
    ) == 1

    assert sleeps == []


def test_candidate_analysis_has_no_blanket_request_delay():
    source = Path(
        "services/candidate_job_analysis_service.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "REQUEST_DELAY_SECONDS"
        not in source
    )

    assert (
        "time.sleep("
        not in source
    )
