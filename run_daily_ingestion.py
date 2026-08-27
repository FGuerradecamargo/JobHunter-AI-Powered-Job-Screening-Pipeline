from __future__ import annotations

import argparse
import os
from dataclasses import asdict
from pprint import pprint

from dotenv import load_dotenv

from migrate_global_job_ingestion import (
    migrate,
)
from services.daily_ingestion_service import (
    DailyIngestionService,
)
from services.job_archive_service import (
    JobArchiveService,
)
from services.gmail_background_sync_service import (
    GmailBackgroundSyncService,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run JobHunter daily background ingestion."
        )
    )

    parser.add_argument(
        "--skip-apis",
        action="store_true",
        help=(
            "Run maintenance without calling "
            "external job APIs."
        ),
    )

    parser.add_argument(
        "--skip-gmail",
        action="store_true",
        help=(
            "Run maintenance without syncing Gmail."
        ),
    )

    parser.add_argument(
        "--day-index",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--archive-days",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--jooble-results",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--adzuna-results",
        type=int,
        default=20,
    )

    return parser.parse_args()


def main() -> None:
    load_dotenv()

    args = parse_args()

    print("=" * 60)
    print("JOBHUNTER - DAILY INGESTION")
    print("=" * 60)

    print()
    print("[1/4] Database migration")
    migrate()
    print("OK")

    if args.skip_apis:
        print()
        print("[2/4] Global API ingestion")
        print("SKIPPED")
    else:
        print()
        print("[2/4] Global API ingestion")

        ingestion = (
            DailyIngestionService().run(
                day_index=args.day_index,
                jooble_results_per_query=(
                    args.jooble_results
                ),
                adzuna_results_per_query=(
                    args.adzuna_results
                ),
            )
        )

        pprint(
            asdict(ingestion)
        )

    if args.skip_gmail:
        print()
        print("[3/4] Gmail ingestion")
        print("SKIPPED")
    else:
        print()
        print("[3/4] Gmail ingestion")

        client_id = os.getenv(
            "GOOGLE_OAUTH_CLIENT_ID"
        )

        client_secret = os.getenv(
            "GOOGLE_OAUTH_CLIENT_SECRET"
        )

        if not client_id:
            raise RuntimeError(
                "GOOGLE_OAUTH_CLIENT_ID not found."
            )

        if not client_secret:
            raise RuntimeError(
                "GOOGLE_OAUTH_CLIENT_SECRET not found."
            )

        gmail_result = (
            GmailBackgroundSyncService(
                client_id=client_id,
                client_secret=client_secret,
            ).run(
                max_results_per_user=100,
                processing_limit_per_user=100,
            )
        )

        pprint(
            asdict(gmail_result)
        )

    print()
    print("[4/4] Archive stale jobs")

    archived = (
        JobArchiveService()
        .archive_stale_global_jobs(
            stale_after_days=(
                args.archive_days
            )
        )
    )

    print(
        "Archived:",
        archived,
    )

    print()
    print("=" * 60)
    print("DAILY INGESTION COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
