"""Bounded, credential-free HTTP transport for public employer board feeds."""
import json
import re
import time
from urllib.parse import urlsplit

import requests


class BoardError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Employer board unavailable ({code}).")


def validate_endpoint(url: str) -> None:
    patterns = {
        "api.lever.co": r"/v0/postings/[A-Za-z0-9][A-Za-z0-9_-]{0,127}",
        "api.eu.lever.co": r"/v0/postings/[A-Za-z0-9][A-Za-z0-9_-]{0,127}",
        "api.ashbyhq.com": r"/posting-api/job-board/[A-Za-z0-9][A-Za-z0-9_-]{0,127}",
    }
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == "https" and parts.netloc in patterns
                 and re.fullmatch(patterns[parts.netloc], parts.path)
                 and not parts.query and not parts.fragment)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise BoardError("invalid_endpoint")


class BoardHTTPClient:
    MAX_BYTES = 8 * 1024 * 1024
    TIMEOUT = (5, 20)
    RETRY_STATUSES = {429, 502, 503, 504}

    def __init__(self, session_factory=requests.Session, sleep=time.sleep):
        self._session_factory = session_factory
        self._sleep = sleep

    def get_json(self, url: str, *, params: dict) -> object:
        validate_endpoint(url)
        # A fresh session cannot leak cookies/auth from one employer to another.
        with self._session_factory() as session:
            session.trust_env = False  # No ambient .netrc credentials or proxies.
            for attempt in range(3):
                retry_delay = 0.5 * (attempt + 1)
                try:
                    with session.get(url, params=params, timeout=self.TIMEOUT,
                                     allow_redirects=False, stream=True,
                                     headers={"Accept": "application/json"}) as response:
                        status = response.status_code
                        if status in self.RETRY_STATUSES:
                            if attempt == 2:
                                raise BoardError("http_retry_exhausted")
                            after = response.headers.get("Retry-After", "")
                            if after:
                                # Long or HTTP-date retry hints belong to the scheduler.
                                if not re.fullmatch(r"[0-9]{1,3}", after) or int(after) > 5:
                                    raise BoardError("rate_limited")
                                retry_delay = max(retry_delay, int(after))
                        elif status != 200:
                            raise BoardError("http_status")
                        else:
                            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                            if content_type != "application/json":
                                raise BoardError("content_type")
                            payload = bytearray()
                            for chunk in response.iter_content(chunk_size=65536):
                                payload.extend(chunk)
                                if len(payload) > self.MAX_BYTES:
                                    raise BoardError("response_too_large")
                            try:
                                return json.loads(payload)
                            except (ValueError, UnicodeError, RecursionError):
                                raise BoardError("invalid_json") from None
                except (requests.Timeout, requests.ConnectionError):
                    if attempt == 2:
                        raise BoardError("transport_retry_exhausted") from None
                except requests.RequestException:
                    raise BoardError("transport_error") from None
                self._sleep(retry_delay)
        raise BoardError("transport_error")
