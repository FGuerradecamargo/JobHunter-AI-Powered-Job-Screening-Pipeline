import json
from dataclasses import asdict
from pathlib import Path

from models.job import Job
from services.job_matcher import JobMatcher
from services.job_enricher import JobEnricher


BASE_DIR = Path(__file__).resolve().parent
RAW_JOBS_FILE = BASE_DIR / "jobs_raw.json"
MATCHED_JOBS_FILE = BASE_DIR / "jobs_matched.json"
ANALYZED_JOBS_FILE = BASE_DIR / "jobs_analyzed.json"
REVIEW_JOBS_FILE = BASE_DIR / "jobs_review.json"


def load_jobs() -> list[Job]:
    if not RAW_JOBS_FILE.exists():
        raise FileNotFoundError(
            "jobs_raw.json não encontrado. Execute primeiro: python main.py"
        )

    jobs_data = json.loads(
        RAW_JOBS_FILE.read_text(encoding="utf-8")
    )

    return [
        Job(**job_data)
        for job_data in jobs_data
    ]


def main() -> None:
    matcher = JobMatcher()
    enricher = JobEnricher()
    jobs = load_jobs()

    analyses: dict[str, dict] = {}

    for job in jobs:
        enricher.enrich(job)

        analysis = matcher.analyze(job)
        job.score = analysis["score"]
        analyses[job.id] = analysis

    sorted_jobs = sorted(
        jobs,
        key=lambda job: job.score if job.score is not None else 0,
        reverse=True,
    )

    relevant_jobs = [
        job
        for job in sorted_jobs
        if matcher.is_relevant(job)
    ]

    review_jobs = [
        job
        for job in sorted_jobs
        if matcher.classify(job) == matcher.REVIEW
    ]

    ANALYZED_JOBS_FILE.write_text(
        json.dumps(
            [asdict(job) for job in sorted_jobs],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"{len(sorted_jobs)} vagas analisadas salvas em: "
        f"{ANALYZED_JOBS_FILE}"
    )

    MATCHED_JOBS_FILE.write_text(
        json.dumps(
            [asdict(job) for job in relevant_jobs],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"{len(relevant_jobs)} vagas relevantes salvas em: "
        f"{MATCHED_JOBS_FILE}"
    )

    REVIEW_JOBS_FILE.write_text(
        json.dumps(
            [asdict(job) for job in review_jobs],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"{len(review_jobs)} vagas para revisão salvas em: "
        f"{REVIEW_JOBS_FILE}"
    )


if __name__ == "__main__":
    main()