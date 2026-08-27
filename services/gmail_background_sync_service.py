from __future__ import annotations

from dataclasses import dataclass

from services.gmail_connection_repository import (
    GmailConnectionRepository,
)
from services.gmail_job_processor import (
    GmailJobProcessor,
)
from services.gmail_sync_service import (
    GmailSyncService,
)


@dataclass
class GmailUserBackgroundResult:
    user_id: str
    success: bool
    messages_found: int = 0
    new_messages: int = 0
    jobs_found: int = 0
    jobs_created: int = 0
    jobs_updated: int = 0
    jobs_unchanged: int = 0
    error: str | None = None


@dataclass
class GmailBackgroundSyncResult:
    users_found: int
    users_succeeded: int
    users_failed: int
    results: list[GmailUserBackgroundResult]


class GmailBackgroundSyncService:

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        connection_repository: (
            GmailConnectionRepository | None
        ) = None,
    ) -> None:
        self._connection_repository = (
            connection_repository
            or GmailConnectionRepository()
        )

        self._sync_service = GmailSyncService(
            client_id=client_id,
            client_secret=client_secret,
            gmail_connection_repository=(
                self._connection_repository
            ),
        )

        self._processor = GmailJobProcessor()

    def run(
        self,
        max_results_per_user: int = 100,
        processing_limit_per_user: int = 100,
    ) -> GmailBackgroundSyncResult:

        user_ids = (
            self._connection_repository
            .list_connected_user_ids()
        )

        results = []

        succeeded = 0
        failed = 0

        for user_id in user_ids:
            try:
                sync_result = (
                    self._sync_service
                    .sync_recent_job_alerts(
                        user_id=user_id,
                        max_results=(
                            max_results_per_user
                        ),
                    )
                )

                processing_result = (
                    self._processor
                    .process_pending_messages(
                        user_id=user_id,
                        limit=(
                            processing_limit_per_user
                        ),
                    )
                )

                results.append(
                    GmailUserBackgroundResult(
                        user_id=user_id,
                        success=True,
                        messages_found=(
                            sync_result
                            .total_messages_found
                        ),
                        new_messages=(
                            sync_result
                            .new_messages_found
                        ),
                        jobs_found=(
                            processing_result
                            .jobs_found
                        ),
                        jobs_created=(
                            processing_result
                            .jobs_created
                        ),
                        jobs_updated=(
                            processing_result
                            .jobs_updated
                        ),
                        jobs_unchanged=(
                            processing_result
                            .jobs_unchanged
                        ),
                    )
                )

                succeeded += 1

            except Exception as error:
                results.append(
                    GmailUserBackgroundResult(
                        user_id=user_id,
                        success=False,
                        error=str(error),
                    )
                )

                failed += 1

                print(
                    "[GMAIL BACKGROUND ERROR]",
                    user_id,
                    "|",
                    repr(error),
                )

        return GmailBackgroundSyncResult(
            users_found=len(user_ids),
            users_succeeded=succeeded,
            users_failed=failed,
            results=results,
        )
