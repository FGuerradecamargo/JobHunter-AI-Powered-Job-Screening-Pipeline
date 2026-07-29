import pytest
from urllib.parse import parse_qs, urlparse

from services.gmail_oauth_service import (
    GMAIL_READONLY_SCOPE,
    GmailOAuthService,
)


def test_creates_google_authorization_url():
    service = GmailOAuthService(
        client_id="example-client-id",
        client_secret="example-client-secret",
        redirect_uri="http://localhost:8501",
    )

    authorization_url, state = (
        service.create_authorization_url()
    )

    assert authorization_url.startswith(
        "https://accounts.google.com/"
    )

    assert "access_type=offline" in authorization_url
    assert "prompt=consent" in authorization_url
    assert state

    parsed_url = urlparse(authorization_url)
    query_parameters = parse_qs(parsed_url.query)

    assert GMAIL_READONLY_SCOPE in query_parameters["scope"]


def test_requires_client_id():
    with pytest.raises(
        RuntimeError,
        match="GOOGLE_OAUTH_CLIENT_ID",
    ):
        GmailOAuthService(
            client_id="",
            client_secret="example-secret",
            redirect_uri="http://localhost:8501",
        )


def test_requires_client_secret():
    with pytest.raises(
        RuntimeError,
        match="GOOGLE_OAUTH_CLIENT_SECRET",
    ):
        GmailOAuthService(
            client_id="example-client-id",
            client_secret="",
            redirect_uri="http://localhost:8501",
        )


def test_requires_redirect_uri():
    with pytest.raises(
        RuntimeError,
        match="GOOGLE_OAUTH_REDIRECT_URI",
    ):
        GmailOAuthService(
            client_id="example-client-id",
            client_secret="example-secret",
            redirect_uri="",
        )