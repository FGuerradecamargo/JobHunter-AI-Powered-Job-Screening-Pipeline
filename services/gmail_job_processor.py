from __future__ import annotations

from dataclasses import dataclass

from parser.email_job_parser import (
    extract_jobs_from_email,
)
from services.database import (
    upsert_raw_job,
)
from services.gmail_message_repository import (
    GmailMessageRepository,
)
from services.job_source_repository import (
    JobSourceRepository,
)


@dataclass(frozen=True)
class GmailJobProcessingResult:
    messages_selected: int
    messages_processed: int
    messages_failed: int
    messages_without_html: int
    jobs_found: int
    jobs_created: int
    jobs_updated: int
    jobs_unchanged: int
    candidate_links_created: int


class GmailJobProcessor:
    def __init__(
        self,
        gmail_message_repository: (
            GmailMessageRepository | None
        ) = None,
        job_source_repository: (
            JobSourceRepository | None
        ) = None,
    ) -> None:
        self._gmail_message_repository = (
            gmail_message_repository
            or GmailMessageRepository()
        )

        self._job_source_repository = (
            job_source_repository
            or JobSourceRepository()
        )

    def process_pending_messages(
        self,
        user_id: str,
        candidate_id: str,
        limit: int = 5,
    ) -> GmailJobProcessingResult:
        if not user_id:
            raise ValueError(
                "User ID is required."
            )

        if not candidate_id:
            raise ValueError(
                "Candidate ID is required."
            )

        if limit <= 0:
            raise ValueError(
                "Limit must be greater than zero."
            )

        pending_messages = (
            self._gmail_message_repository
            .list_pending(
                user_id=user_id,
                limit=limit,
            )
        )

        messages_processed = 0
        messages_failed = 0
        messages_without_html = 0

        jobs_found = 0
        jobs_created = 0
        jobs_updated = 0
        jobs_unchanged = 0
        candidate_links_created = 0

        for message in pending_messages:
            message_id = message[
                "gmail_message_id"
            ]

            raw_html = (
                message.get("raw_html")
                or ""
            )

            if not raw_html.strip():
                messages_without_html += 1

                self._gmail_message_repository.mark_failed(
                    user_id=user_id,
                    gmail_message_id=message_id,
                    error_message=(
                        "The Gmail message does not "
                        "contain HTML content."
                    ),
                )

                continue

            try:
                parsed = extract_jobs_from_email(
                    html=raw_html,
                    sender=message.get(
                        "sender",
                        "",
                    ),
                )

                jobs = parsed.jobs

                jobs_found += len(jobs)

                for job in jobs.values():
                    result = upsert_raw_job(job)

                    source_type = (
                        "gmail_"
                        + parsed.source
                    )

                    self._job_source_repository.add_source(
                        job_id=job.id,
                        user_id=user_id,
                        source_type=source_type,
                    )

                    if result == "created":
                        jobs_created += 1

                    elif result == "updated":
                        jobs_updated += 1

                    else:
                        jobs_unchanged += 1

                self._gmail_message_repository.mark_processed(
                    user_id=user_id,
                    gmail_message_id=message_id,
                )

                messages_processed += 1

            except Exception as error:
                messages_failed += 1

                self._gmail_message_repository.mark_failed(
                    user_id=user_id,
                    gmail_message_id=message_id,
                    error_message=str(error),
                )

        return GmailJobProcessingResult(
            messages_selected=len(
                pending_messages
            ),
            messages_processed=(
                messages_processed
            ),
            messages_failed=messages_failed,
            messages_without_html=(
                messages_without_html
            ),
            jobs_found=jobs_found,
            jobs_created=jobs_created,
            jobs_updated=jobs_updated,
            jobs_unchanged=jobs_unchanged,
            candidate_links_created=(
                candidate_links_created
            ),
        )