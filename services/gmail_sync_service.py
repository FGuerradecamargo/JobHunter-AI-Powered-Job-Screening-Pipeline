from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from models.gmail_connection import GmailConnection
from services.gmail_connection_repository import (
    GmailConnectionRepository,
)
from services.gmail_message_repository import (
    GmailMessageRepository,
)

GMAIL_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly"
)

DEFAULT_JOB_ALERT_QUERY = (
    "newer_than:30d "
    "from:jobalerts-noreply@linkedin.com "
    'subject:("new job" OR "new jobs")'
)


@dataclass(frozen=True)
class GmailMessageSummary:
    message_id: str
    thread_id: Optional[str]
    history_id: Optional[str]
    internal_date: Optional[str]
    received_at: Optional[str]
    subject: str
    sender: str
    snippet: str


@dataclass(frozen=True)
class GmailSyncResult:
    gmail_address: str
    total_messages_found: int
    new_messages_found: int
    skipped_existing: int
    messages: list[GmailMessageSummary]
    latest_history_id: Optional[str]


class GmailSyncService:
    def __init__(
            self,
            client_id: str,
            client_secret: str,
            gmail_connection_repository: (
                    GmailConnectionRepository | None
            ) = None,
            gmail_message_repository: (
                    GmailMessageRepository | None
            ) = None,
    ) -> None:
        if not client_id:
            raise ValueError(
                "Google OAuth client ID is required."
            )

        if not client_secret:
            raise ValueError(
                "Google OAuth client secret is required."
            )

        self._client_id = client_id
        self._client_secret = client_secret

        self._gmail_connection_repository = (
                gmail_connection_repository
                or GmailConnectionRepository()
        )

        self._gmail_message_repository = (
                gmail_message_repository
                or GmailMessageRepository()
        )

    def sync_recent_job_alerts(
            self,
            user_id: str,
            query: str = DEFAULT_JOB_ALERT_QUERY,
            max_results: int = 100,
    ) -> GmailSyncResult:
        gmail_connection = (
            self._gmail_connection_repository
            .get_by_user_id(user_id)
        )

        if gmail_connection is None:
            raise ValueError(
                "This user does not have a Gmail "
                "connection."
            )

        if (
                gmail_connection.connection_status
                != "connected"
        ):
            raise ValueError(
                "The Gmail connection is not active."
            )

        credentials = self._build_credentials(
            gmail_connection
        )

        if credentials.expired:
            credentials.refresh(Request())

        gmail_service = build(
            "gmail",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

        response = (
            gmail_service
            .users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
            )
            .execute()
        )

        message_references = response.get(
            "messages",
            [],
        )

        new_messages: list[
            GmailMessageSummary
        ] = []

        skipped_existing = 0
        latest_history_id: Optional[str] = None

        for reference in message_references:
            message_id = reference.get("id")

            if not message_id:
                continue

            if self._gmail_message_repository.exists(
                    user_id=user_id,
                    gmail_message_id=message_id,
            ):
                skipped_existing += 1
                continue

            message = (
                gmail_service
                .users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="metadata",
                    metadataHeaders=[
                        "Subject",
                        "From",
                    ],
                )
                .execute()
            )

            summary = self._to_message_summary(
                message
            )

            was_registered = (
                self._gmail_message_repository
                .register_if_new(
                    user_id=user_id,
                    gmail_message_id=(
                        summary.message_id
                    ),
                    gmail_thread_id=(
                        summary.thread_id
                    ),
                    received_at=(
                        summary.received_at
                    ),
                )
            )

            if not was_registered:
                skipped_existing += 1
                continue

            new_messages.append(summary)

            latest_history_id = (
                self._newer_history_id(
                    latest_history_id,
                    summary.history_id,
                )
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        self._save_refreshed_credentials(
            gmail_connection=gmail_connection,
            credentials=credentials,
            last_history_id=latest_history_id,
            last_sync_at=now,
        )

        return GmailSyncResult(
            gmail_address=(
                gmail_connection.gmail_address
            ),
            total_messages_found=len(
                message_references
            ),
            new_messages_found=len(
                new_messages
            ),
            skipped_existing=skipped_existing,
            messages=new_messages,
            latest_history_id=latest_history_id,
        )

    def _build_credentials(
            self,
            gmail_connection: GmailConnection,
    ) -> Credentials:
        return Credentials(
            token=gmail_connection.access_token,
            refresh_token=(
                gmail_connection.refresh_token
            ),
            token_uri=(
                "https://oauth2.googleapis.com/token"
            ),
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=(
                    gmail_connection.scopes
                    or [GMAIL_READONLY_SCOPE]
            ),
        )

    def _save_refreshed_credentials(
            self,
            gmail_connection: GmailConnection,
            credentials: Credentials,
            last_history_id: Optional[str],
            last_sync_at: str,
    ) -> None:
        token_expiry = None

        if credentials.expiry is not None:
            expiry = credentials.expiry

            if expiry.tzinfo is None:
                expiry = expiry.replace(
                    tzinfo=timezone.utc
                )

            token_expiry = expiry.isoformat()

        self._gmail_connection_repository.save(
            GmailConnection(
                user_id=gmail_connection.user_id,
                gmail_address=(
                    gmail_connection.gmail_address
                ),
                refresh_token=(
                    gmail_connection.refresh_token
                ),
                access_token=credentials.token,
                token_expiry=token_expiry,
                scopes=(
                    list(credentials.scopes)
                    if credentials.scopes
                    else gmail_connection.scopes
                ),
                last_history_id=last_history_id,
                last_sync_at=last_sync_at,
                connection_status="connected",
            )
        )

    @classmethod
    def _to_message_summary(
            cls,
            message: dict[str, Any],
    ) -> GmailMessageSummary:
        payload = message.get(
            "payload",
            {},
        )

        headers = payload.get(
            "headers",
            [],
        )

        header_values = {
            str(
                header.get("name", "")
            ).lower(): str(
                header.get("value", "")
            )
            for header in headers
        }

        internal_date = message.get(
            "internalDate"
        )

        return GmailMessageSummary(
            message_id=str(
                message.get("id", "")
            ),
            thread_id=message.get("threadId"),
            history_id=message.get("historyId"),
            internal_date=internal_date,
            received_at=(
                cls._internal_date_to_iso(
                    internal_date
                )
            ),
            subject=header_values.get(
                "subject",
                "",
            ),
            sender=header_values.get(
                "from",
                "",
            ),
            snippet=str(
                message.get("snippet", "")
            ),
        )

    @staticmethod
    def _internal_date_to_iso(
            internal_date: Any,
    ) -> Optional[str]:
        if internal_date is None:
            return None

        try:
            timestamp_seconds = (
                    int(str(internal_date)) / 1000
            )

            return datetime.fromtimestamp(
                timestamp_seconds,
                tz=timezone.utc,
            ).isoformat()

        except (TypeError, ValueError):
            return None

    @staticmethod
    def _newer_history_id(
            current_history_id: Optional[str],
            candidate_history_id: Optional[str],
    ) -> Optional[str]:
        if not candidate_history_id:
            return current_history_id

        if not current_history_id:
            return candidate_history_id

        try:
            if int(candidate_history_id) > int(
                    current_history_id
            ):
                return candidate_history_id

        except ValueError:
            return candidate_history_id

        return current_history_id
