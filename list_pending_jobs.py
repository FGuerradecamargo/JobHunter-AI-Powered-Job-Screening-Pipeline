import json
from pathlib import Path


MATCHED_JOBS_FILE = Path("jobs_matched.json")
AI_CACHE_FILE = Path("jobs_ai_recommended.json")


def deduplicate_jobs(
    jobs: list[dict],
) -> list[dict]:
    unique_jobs: list[dict] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for job in jobs:
        key = (
            (job.get("title") or "").strip().lower(),
            (job.get("company") or "").strip().lower(),
            (job.get("location") or "").strip().lower(),
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)
        unique_jobs.append(job)

    return unique_jobs


def main() -> None:
    matched_jobs = json.loads(
        MATCHED_JOBS_FILE.read_text(
            encoding="utf-8"
        )
    )

    cached_jobs = json.loads(
        AI_CACHE_FILE.read_text(
            encoding="utf-8"
        )
    )

    cached_ids = {
        str(item["job"]["id"])
        for item in cached_jobs
    }

    pending_jobs = [
        job
        for job in matched_jobs
        if str(job["id"]) not in cached_ids
    ]

    pending_jobs = deduplicate_jobs(
        pending_jobs
    )

    for index, job in enumerate(
        pending_jobs,
        start=1,
    ):
        print(
            f"{index}. "
            f"{job.get('title')} — "
            f"{job.get('company')} — "
            f"{job.get('location')}"
        )

    print()
    print(
        f"Total pendentes: {len(pending_jobs)}"
    )


if __name__ == "__main__":
    main()