from __future__ import annotations

from services.account_action_token_service import (
    AccountActionTokenService,
)
from services.account_recovery_service import (
    AccountRecoveryService,
)
from services.password_reset_service import (
    PasswordResetService,
)
from services.public_url_service import (
    PublicUrlConfigurationError,
    PublicUrlService,
)
from services.transactional_email_service import (
    TransactionalEmailError,
    TransactionalEmailService,
)


def test_public_response_is_identical_for_existing_and_missing_accounts(
    monkeypatch,
):
    responses = []
    sent = []

    monkeypatch.setattr(
        PasswordResetService,
        "request_reset_token",
        staticmethod(
            lambda email: (
                "raw-secret-reset-token"
                if "existing" in email
                else None
            )
        ),
    )

    monkeypatch.setattr(
        PublicUrlService,
        "password_reset_url",
        classmethod(
            lambda cls, token: (
                "https://workpilot.example"
                f"/reset-password?token={token}"
            )
        ),
    )

    def fake_send_email(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        fake_send_email,
    )

    responses.append(
        AccountRecoveryService
        .request_password_reset(
            "existing@example.com"
        )
    )

    responses.append(
        AccountRecoveryService
        .request_password_reset(
            "missing@example.com"
        )
    )

    assert (
        responses[0]
        == responses[1]
        == AccountRecoveryService
        .GENERIC_RESET_RESPONSE
    )

    assert len(sent) == 1


def test_raw_token_never_appears_in_public_response_or_idempotency_key(
    monkeypatch,
):
    raw_token = (
        "super-secret-reset-token-value"
    )

    captured = {}

    monkeypatch.setattr(
        PasswordResetService,
        "request_reset_token",
        staticmethod(
            lambda email: raw_token
        ),
    )

    monkeypatch.setattr(
        PublicUrlService,
        "password_reset_url",
        classmethod(
            lambda cls, token: (
                "https://workpilot.example"
                f"/reset-password?token={token}"
            )
        ),
    )

    def fake_send_email(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        fake_send_email,
    )

    response = (
        AccountRecoveryService
        .request_password_reset(
            "user@example.com"
        )
    )

    assert raw_token not in response

    assert (
        raw_token
        not in captured[
            "idempotency_key"
        ]
    )

    expected_hash = (
        AccountActionTokenService
        .hash_token(raw_token)
    )

    assert (
        captured["idempotency_key"]
        == (
            "password-reset-"
            f"{expected_hash}"
        )
    )

    # Raw secret exists only inside the
    # private link delivered by email.
    assert (
        raw_token
        in captured["html"]
    )


def test_email_provider_failure_keeps_same_public_response(
    monkeypatch,
):
    raw_token = (
        "provider-failure-secret-token"
    )

    monkeypatch.setattr(
        PasswordResetService,
        "request_reset_token",
        staticmethod(
            lambda email: raw_token
        ),
    )

    monkeypatch.setattr(
        PublicUrlService,
        "password_reset_url",
        classmethod(
            lambda cls, token: (
                "https://workpilot.example"
                f"/reset-password?token={token}"
            )
        ),
    )

    def fail_send(**kwargs):
        raise TransactionalEmailError(
            "provider internal failure"
        )

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        fail_send,
    )

    response = (
        AccountRecoveryService
        .request_password_reset(
            "existing@example.com"
        )
    )

    assert (
        response
        == AccountRecoveryService
        .GENERIC_RESET_RESPONSE
    )

    assert raw_token not in response

    assert (
        "provider internal failure"
        not in response
    )


def test_reset_url_is_html_escaped_before_email(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        PasswordResetService,
        "request_reset_token",
        staticmethod(
            lambda email: "raw-token"
        ),
    )

    monkeypatch.setattr(
        PublicUrlService,
        "password_reset_url",
        classmethod(
            lambda cls, token: (
                "https://workpilot.example"
                f"/reset-password?token={token}"
                '&next="unsafe"'
            )
        ),
    )

    def fake_send_email(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        fake_send_email,
    )

    (
        AccountRecoveryService
        .request_password_reset(
            "user@example.com"
        )
    )

    html = captured["html"]

    assert "&amp;" in html
    assert "&quot;unsafe&quot;" in html
    assert '"unsafe"' not in html


def test_public_url_configuration_failure_does_not_attempt_email_delivery(
    monkeypatch,
):
    monkeypatch.setattr(
        PasswordResetService,
        "request_reset_token",
        staticmethod(
            lambda email: "unused-secret-token"
        ),
    )

    def fail_url(
        cls,
        token,
    ):
        raise PublicUrlConfigurationError(
            "private configuration detail"
        )

    monkeypatch.setattr(
        PublicUrlService,
        "password_reset_url",
        classmethod(fail_url),
    )

    def must_not_send(**kwargs):
        raise AssertionError(
            "Email must not be sent "
            "without a valid public URL."
        )

    monkeypatch.setattr(
        TransactionalEmailService,
        "send_email",
        must_not_send,
    )

    response = (
        AccountRecoveryService
        .request_password_reset(
            "user@example.com"
        )
    )

    assert (
        response
        == AccountRecoveryService
        .GENERIC_RESET_RESPONSE
    )

    assert (
        "private configuration detail"
        not in response
    )
