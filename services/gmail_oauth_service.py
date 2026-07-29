from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build


GMAIL_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly"
)


@dataclass(frozen=True)
class GmailOAuthResult:
    gmail_address: str
    access_token: str
    refresh_token: str
    token_expiry: Optional[str]
    scopes: list[str]


@dataclass(frozen=True)
class GmailAuthorizationRequest:
    authorization_url: str
    state: str
    code_verifier: str


class GmailOAuthService:
    def __init__(
            self,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            redirect_uri: Optional[str] = None,
    ) -> None:
        self._client_id = (
            os.getenv("GOOGLE_OAUTH_CLIENT_ID")
            if client_id is None
            else client_id
        )

        self._client_secret = (
            os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
            if client_secret is None
            else client_secret
        )

        self._redirect_uri = (
            os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
            if redirect_uri is None
            else redirect_uri
        )

        if not self._client_id:
            raise RuntimeError(
                "GOOGLE_OAUTH_CLIENT_ID is not configured."
            )

        if not self._client_secret:
            raise RuntimeError(
                "GOOGLE_OAUTH_CLIENT_SECRET is not configured."
            )

        if not self._redirect_uri:
            raise RuntimeError(
                "GOOGLE_OAUTH_REDIRECT_URI is not configured."
            )

    def create_authorization_url(
            self,
    ) -> GmailAuthorizationRequest:
        flow = self._create_flow(
            autogenerate_code_verifier=True
        )

        authorization_url, state = (
            flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )
        )

        if not flow.code_verifier:
            raise RuntimeError(
                "OAuth code verifier was not generated."
            )

        return GmailAuthorizationRequest(
            authorization_url=authorization_url,
            state=state,
            code_verifier=flow.code_verifier,
        )

    def exchange_authorization_code(
            self,
            authorization_code: str,
            expected_state: str,
            code_verifier: str,
    ) -> GmailOAuthResult:
        if not authorization_code:
            raise ValueError(
                "Google authorization code is required."
            )

        if not expected_state:
            raise ValueError(
                "OAuth state is required."
            )

        if not code_verifier:
            raise ValueError(
                "OAuth code verifier is required."
            )

        flow = self._create_flow(
            state=expected_state,
            code_verifier=code_verifier,
        )

        flow.fetch_token(
            code=authorization_code,
        )

        credentials = flow.credentials

        if not credentials.token:
            raise RuntimeError(
                "Google did not return an access token."
            )

        if not credentials.refresh_token:
            raise RuntimeError(
                "Google did not return a refresh token."
            )

        gmail_address = self._get_gmail_address(
            credentials
        )

        token_expiry = None

        if credentials.expiry is not None:
            expiry = credentials.expiry

            if expiry.tzinfo is None:
                expiry = expiry.replace(
                    tzinfo=timezone.utc
                )

            token_expiry = expiry.isoformat()

        return GmailOAuthResult(
            gmail_address=gmail_address,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_expiry=token_expiry,
            scopes=list(
                credentials.scopes
                or [GMAIL_READONLY_SCOPE]
            ),
        )

    def _create_flow(
            self,
            state: Optional[str] = None,
            code_verifier: Optional[str] = None,
            autogenerate_code_verifier: bool = False,
    ) -> Flow:
        client_config = {
            "web": {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "auth_uri": (
                    "https://accounts.google.com/o/oauth2/auth"
                ),
                "token_uri": (
                    "https://oauth2.googleapis.com/token"
                ),
                "redirect_uris": [
                    self._redirect_uri
                ],
            }
        }

        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=[GMAIL_READONLY_SCOPE],
            state=state,
            code_verifier=code_verifier,
            autogenerate_code_verifier=(
                autogenerate_code_verifier
            ),
        )

        flow.redirect_uri = self._redirect_uri

        return flow

    @staticmethod
    def _get_gmail_address(
        credentials: Credentials,
    ) -> str:
        gmail_service = build(
            "gmail",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

        profile = (
            gmail_service
            .users()
            .getProfile(userId="me")
            .execute()
        )

        gmail_address = (
            profile.get("emailAddress", "")
            .strip()
            .lower()
        )

        if not gmail_address:
            raise RuntimeError(
                "Google did not return the Gmail address."
            )

        return gmail_address

    @dataclass(frozen=True)
    class GmailAuthorizationRequest:
        authorization_url: str
        state: str
        code_verifier: str