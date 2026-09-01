from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

import services.transactional_email_service as email_module
from services.transactional_email_service import (
    TransactionalEmailError,
    TransactionalEmailService,
)


@pytest.fixture
def configured_email(
    monkeypatch,
):
    monkeypatch.setenv(
        "RESEND_API_KEY",
        "re_test_secret_value",
    )

    monkeypatch.setenv(
        "EMAIL_FROM",
        "WorkPilot <security@example.com>",
    )


def test_missing_configuration_fails_closed(
    monkeypatch,
):
    monkeypatch.delenv(
        "RESEND_API_KEY",
        raising=False,
    )

    monkeypatch.delenv(
        "EMAIL_FROM",
        raising=False,
    )

    with pytest.raises(
        TransactionalEmailError,
        match=(
            "Transactional email service "
            "is not configured"
        ),
    ):
        TransactionalEmailService.send_email(
            to_email="user@example.com",
            subject="Test",
            html="<p>Test</p>",
        )


def test_successful_send_uses_expected_request(
    monkeypatch,
    configured_email,
):
    captured = {}

    def fake_post(
        url,
        *,
        headers,
        json,
        timeout,
    ):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout

        return SimpleNamespace(
            status_code=200
        )

    monkeypatch.setattr(
        email_module.requests,
        "post",
        fake_post,
    )

    TransactionalEmailService.send_email(
        to_email=" user@example.com ",
        subject=" Password reset ",
        html="<p>Reset</p>",
        idempotency_key=(
            "password-reset-test-key"
        ),
    )

    assert (
        captured["url"]
        == TransactionalEmailService
        ._RESEND_ENDPOINT
    )

    assert (
        captured["headers"]["Authorization"]
        == "Bearer re_test_secret_value"
    )

    assert (
        captured["headers"]["Content-Type"]
        == "application/json"
    )

    assert (
        captured["headers"]["Idempotency-Key"]
        == "password-reset-test-key"
    )

    assert captured["json"] == {
        "from": (
            "WorkPilot <security@example.com>"
        ),
        "to": [
            "user@example.com"
        ],
        "subject": "Password reset",
        "html": "<p>Reset</p>",
    }

    assert (
        captured["timeout"]
        == TransactionalEmailService
        ._TIMEOUT_SECONDS
    )


def test_idempotency_header_is_optional(
    monkeypatch,
    configured_email,
):
    captured = {}

    def fake_post(
        url,
        *,
        headers,
        json,
        timeout,
    ):
        captured["headers"] = headers

        return SimpleNamespace(
            status_code=202
        )

    monkeypatch.setattr(
        email_module.requests,
        "post",
        fake_post,
    )

    TransactionalEmailService.send_email(
        to_email="user@example.com",
        subject="Verification",
        html="<p>Verify</p>",
    )

    assert (
        "Idempotency-Key"
        not in captured["headers"]
    )


def test_network_failure_is_generic_and_hides_inner_error(
    monkeypatch,
    configured_email,
):
    secret_marker = (
        "re_secret_that_must_not_escape"
    )

    monkeypatch.setenv(
        "RESEND_API_KEY",
        secret_marker,
    )

    def fail_post(*args, **kwargs):
        raise requests.RequestException(
            f"network failure {secret_marker}"
        )

    monkeypatch.setattr(
        email_module.requests,
        "post",
        fail_post,
    )

    with pytest.raises(
        TransactionalEmailError
    ) as exc_info:
        TransactionalEmailService.send_email(
            to_email="user@example.com",
            subject="Reset",
            html="<p>Reset</p>",
        )

    assert str(exc_info.value) == (
        "Transactional email service "
        "is temporarily unavailable."
    )

    assert (
        secret_marker
        not in str(exc_info.value)
    )

    assert (
        exc_info.value.__cause__
        is None
    )


def test_http_rejection_is_generic(
    monkeypatch,
    configured_email,
):
    def fake_post(*args, **kwargs):
        return SimpleNamespace(
            status_code=429,
            text=(
                "provider-private-error"
            ),
        )

    monkeypatch.setattr(
        email_module.requests,
        "post",
        fake_post,
    )

    with pytest.raises(
        TransactionalEmailError
    ) as exc_info:
        TransactionalEmailService.send_email(
            to_email="user@example.com",
            subject="Reset",
            html="<p>Reset</p>",
        )

    assert str(exc_info.value) == (
        "Transactional email service "
        "rejected the request."
    )

    assert (
        "provider-private-error"
        not in str(exc_info.value)
    )


@pytest.mark.parametrize(
    (
        "to_email",
        "subject",
        "html",
        "expected",
    ),
    [
        (
            "",
            "Subject",
            "<p>Body</p>",
            "Recipient email is required",
        ),
        (
            "user@example.com",
            "",
            "<p>Body</p>",
            "Email subject is required",
        ),
        (
            "user@example.com",
            "Subject",
            "",
            "Email content is required",
        ),
    ],
)
def test_invalid_message_inputs_are_rejected_before_http(
    monkeypatch,
    configured_email,
    to_email,
    subject,
    html,
    expected,
):
    def must_not_send(*args, **kwargs):
        raise AssertionError(
            "HTTP must not be called."
        )

    monkeypatch.setattr(
        email_module.requests,
        "post",
        must_not_send,
    )

    with pytest.raises(
        ValueError,
        match=expected,
    ):
        TransactionalEmailService.send_email(
            to_email=to_email,
            subject=subject,
            html=html,
        )
