from __future__ import annotations

from urllib.parse import (
    parse_qs,
    urlparse,
)

import pytest

from services.public_url_service import (
    PublicUrlConfigurationError,
    PublicUrlService,
)


def test_https_public_base_url_builds_reset_link(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "https://app.workpilot.example",
    )

    url = (
        PublicUrlService
        .password_reset_url(
            "reset-token-value"
        )
    )

    assert url == (
        "https://app.workpilot.example"
        "/reset-password"
        "?token=reset-token-value"
    )


def test_trailing_slash_is_normalized(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "https://app.workpilot.example/",
    )

    url = (
        PublicUrlService
        .password_reset_url(
            "token"
        )
    )

    assert (
        url
        == (
            "https://app.workpilot.example"
            "/reset-password?token=token"
        )
    )

    assert "//reset-password" not in url


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://[::1]:8501",
    ],
)
def test_http_is_allowed_for_local_development(
    monkeypatch,
    base_url,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        base_url,
    )

    url = (
        PublicUrlService
        .password_reset_url(
            "local-token"
        )
    )

    assert url.startswith(
        f"{base_url}/reset-password?"
    )


def test_non_local_http_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "http://workpilot.example",
    )

    with pytest.raises(
        PublicUrlConfigurationError,
        match="must use HTTPS",
    ):
        (
            PublicUrlService
            .password_reset_url(
                "token"
            )
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "workpilot.example",
        "ftp://workpilot.example",
        "https://workpilot.example?source=x",
        "https://workpilot.example#fragment",
    ],
)
def test_invalid_public_url_configuration_is_rejected(
    monkeypatch,
    base_url,
):
    if base_url:
        monkeypatch.setenv(
            "WORKPILOT_PUBLIC_BASE_URL",
            base_url,
        )
    else:
        monkeypatch.delenv(
            "WORKPILOT_PUBLIC_BASE_URL",
            raising=False,
        )

    with pytest.raises(
        PublicUrlConfigurationError
    ):
        (
            PublicUrlService
            .password_reset_url(
                "token"
            )
        )


def test_reset_token_is_safely_url_encoded(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "https://app.workpilot.example",
    )

    raw_token = (
        "secret token+/=?&value"
    )

    url = (
        PublicUrlService
        .password_reset_url(
            raw_token
        )
    )

    parsed = urlparse(
        url
    )

    query = parse_qs(
        parsed.query
    )

    assert (
        parsed.scheme
        == "https"
    )

    assert (
        parsed.netloc
        == "app.workpilot.example"
    )

    assert (
        parsed.path
        == "/reset-password"
    )

    assert query == {
        "token": [
            raw_token
        ]
    }

    assert (
        raw_token
        not in url
    )


def test_empty_reset_token_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "https://app.workpilot.example",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Password reset token "
            "is required"
        ),
    ):
        (
            PublicUrlService
            .password_reset_url(
                "   "
            )
        )


def test_https_public_base_url_builds_verification_link(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "https://app.workpilot.example",
    )

    url = (
        PublicUrlService
        .email_verification_url(
            "verification-token-value"
        )
    )

    assert url == (
        "https://app.workpilot.example"
        "/verify-email"
        "?token=verification-token-value"
    )


def test_verification_token_is_safely_url_encoded(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "https://app.workpilot.example",
    )

    raw_token = (
        "secret token+/=?&value"
    )

    url = (
        PublicUrlService
        .email_verification_url(
            raw_token
        )
    )

    parsed = urlparse(
        url
    )

    query = parse_qs(
        parsed.query
    )

    assert (
        parsed.path
        == "/verify-email"
    )

    assert query == {
        "token": [
            raw_token
        ]
    }

    assert (
        raw_token
        not in url
    )


def test_empty_verification_token_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "WORKPILOT_PUBLIC_BASE_URL",
        "https://app.workpilot.example",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Email verification token "
            "is required"
        ),
    ):
        (
            PublicUrlService
            .email_verification_url(
                "   "
            )
        )
