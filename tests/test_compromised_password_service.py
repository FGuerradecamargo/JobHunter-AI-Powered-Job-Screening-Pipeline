from __future__ import annotations

import hashlib

import pytest
import requests

from services.compromised_password_service import (
    CompromisedPasswordService,
    PasswordSecurityUnavailableError,
)


class FakeResponse:
    def __init__(
        self,
        text="",
        *,
        error=None,
    ):
        self.text = text
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error


def test_only_sha1_prefix_is_sent(
    monkeypatch,
):
    password = (
        "this is a private password"
    )

    full_hash = hashlib.sha1(
        password.encode("utf-8")
    ).hexdigest().upper()

    expected_prefix = full_hash[:5]
    expected_suffix = full_hash[5:]

    captured = {}

    def fake_get(
        url,
        *,
        headers,
        timeout,
    ):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout

        return FakeResponse(
            f"{expected_suffix}:42"
        )

    monkeypatch.setattr(
        requests,
        "get",
        fake_get,
    )

    count = (
        CompromisedPasswordService
        .breach_count(password)
    )

    assert count == 42

    assert captured["url"].endswith(
        f"/range/{expected_prefix}"
    )

    assert password not in captured["url"]
    assert full_hash not in captured["url"]

    assert captured["headers"][
        "Add-Padding"
    ] == "true"

    assert captured["timeout"] == (
        CompromisedPasswordService
        .TIMEOUT_SECONDS
    )


def test_unseen_password_returns_zero(
    monkeypatch,
):
    def fake_get(
        url,
        *,
        headers,
        timeout,
    ):
        return FakeResponse(
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:5\n"
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB:9"
        )

    monkeypatch.setattr(
        requests,
        "get",
        fake_get,
    )

    assert (
        CompromisedPasswordService
        .breach_count(
            "a unique password example"
        )
        == 0
    )


def test_matching_suffix_is_case_insensitive(
    monkeypatch,
):
    password = (
        "another private password"
    )

    full_hash = hashlib.sha1(
        password.encode("utf-8")
    ).hexdigest().upper()

    suffix = full_hash[5:]

    def fake_get(
        url,
        *,
        headers,
        timeout,
    ):
        return FakeResponse(
            f"{suffix.lower()}:123"
        )

    monkeypatch.setattr(
        requests,
        "get",
        fake_get,
    )

    assert (
        CompromisedPasswordService
        .breach_count(password)
        == 123
    )


def test_malformed_lines_are_ignored(
    monkeypatch,
):
    def fake_get(
        url,
        *,
        headers,
        timeout,
    ):
        return FakeResponse(
            "not-valid\n"
            "ABC:not-a-number\n"
            "also-not-valid"
        )

    monkeypatch.setattr(
        requests,
        "get",
        fake_get,
    )

    assert (
        CompromisedPasswordService
        .breach_count(
            "some sufficiently long password"
        )
        == 0
    )


def test_request_failure_fails_closed(
    monkeypatch,
):
    def fake_get(
        url,
        *,
        headers,
        timeout,
    ):
        raise requests.Timeout(
            "simulated timeout"
        )

    monkeypatch.setattr(
        requests,
        "get",
        fake_get,
    )

    with pytest.raises(
        PasswordSecurityUnavailableError,
        match=(
            "Password security check "
            "is temporarily unavailable"
        ),
    ):
        (
            CompromisedPasswordService
            .breach_count(
                "another sufficiently long password"
            )
        )


def test_http_error_fails_closed(
    monkeypatch,
):
    def fake_get(
        url,
        *,
        headers,
        timeout,
    ):
        return FakeResponse(
            error=requests.HTTPError(
                "simulated HTTP error"
            )
        )

    monkeypatch.setattr(
        requests,
        "get",
        fake_get,
    )

    with pytest.raises(
        PasswordSecurityUnavailableError
    ):
        (
            CompromisedPasswordService
            .breach_count(
                "yet another long password"
            )
        )


def test_is_compromised_uses_breach_count(
    monkeypatch,
):
    monkeypatch.setattr(
        CompromisedPasswordService,
        "breach_count",
        classmethod(
            lambda cls, password: 7
        ),
    )

    assert (
        CompromisedPasswordService
        .is_compromised(
            "any password value"
        )
    )
