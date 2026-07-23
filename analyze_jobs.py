import json
import time
from dataclasses import asdict
from pathlib import Path

from models.job import Job
from services.job_enricher import JobEnricher
from services.job_matcher import JobMatcher

from services.analyzers.hard_filter_analyzer import (
    HardFilterAnalyzer,
)
from services.candidate_profile_loader import (
    load_candidate_profile,
)


BASE_DIR = Path(__file__).resolve().parent

RAW_JOBS_FILE = BASE_DIR / "jobs_raw.json"
ANALYZED_JOBS_FILE = BASE_DIR / "jobs_analyzed.json"
MATCHED_JOBS_FILE = BASE_DIR / "jobs_matched.json"
REVIEW_JOBS_FILE = BASE_DIR / "jobs_review.json"

REQUEST_DELAY_SECONDS = 2

CANDIDATE_PROFILE_FILE = (
    BASE_DIR / "candidate_profile.json"
)


def load_jobs() -> list[Job]:
    if not RAW_JOBS_FILE.exists():
        raise FileNotFoundError(
            "jobs_raw.json não encontrado. "
            "Execute primeiro: python main.py"
        )

    jobs_data = json.loads(
        RAW_JOBS_FILE.read_text(encoding="utf-8")
    )

    return [
        Job(**job_data)
        for job_data in jobs_data
    ]


def load_cached_descriptions() -> dict[str, str]:
    if not ANALYZED_JOBS_FILE.exists():
        return {}

    cached_jobs = json.loads(
        ANALYZED_JOBS_FILE.read_text(encoding="utf-8")
    )

    return {
        job_data["id"]: job_data["description"]
        for job_data in cached_jobs
        if job_data.get("description")
    }


def save_jobs(
    file_path: Path,
    jobs: list[Job],
) -> None:
    file_path.write_text(
        json.dumps(
            [asdict(job) for job in jobs],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main(
    verbose: bool = True,
) -> dict:
    matcher = JobMatcher()
    enricher = JobEnricher()

    profile = load_candidate_profile(
        CANDIDATE_PROFILE_FILE
    )

    hard_filter = HardFilterAnalyzer(
        profile
    )

    jobs = load_jobs()
    cached_descriptions = load_cached_descriptions()

    analyses: dict[str, dict] = {}

    cached_count = 0
    fetched_count = 0
    failed_count = 0

    hard_rejected_count = 0

    for job in jobs:
        cached_description = cached_descriptions.get(job.id)

        if cached_description:
            job.description = cached_description
            cached_count += 1

        else:

            if verbose:
                print(f"Buscando descrição: {job.title}")

            enricher.enrich(job)

            if job.description is None:
                failed_count += 1
            else:
                fetched_count += 1

            time.sleep(REQUEST_DELAY_SECONDS)

        hard_filter_result = hard_filter.analyze(job)

        if hard_filter_result["rejected"]:
            hard_rejected_count += 1

            analysis = {
                "score": -100,
                "reasons": hard_filter_result["reasons"],
            }

            job.score = -100
            job.reasons = hard_filter_result["reasons"]
            job.classification = matcher.NOT_RELEVANT

        else:
            analysis = matcher.analyze(job)

            job.score = analysis["score"]
            job.reasons = analysis["reasons"]
            job.classification = matcher.classify(job)

        analyses[job.id] = analysis

    sorted_jobs = sorted(
        jobs,
        key=lambda job: (
            job.score
            if job.score is not None
            else 0
        ),
        reverse=True,
    )

    relevant_jobs = [
        job
        for job in sorted_jobs
        if matcher.classify(job) == matcher.RELEVANT
    ]

    review_jobs = [
        job
        for job in sorted_jobs
        if matcher.classify(job) == matcher.REVIEW
    ]

    save_jobs(
        ANALYZED_JOBS_FILE,
        sorted_jobs,
    )

    save_jobs(
        MATCHED_JOBS_FILE,
        relevant_jobs,
    )

    save_jobs(
        REVIEW_JOBS_FILE,
        review_jobs,
    )

    if verbose:
        print(f"\nDescrições reutilizadas: {cached_count}")
        print(f"Descrições obtidas agora: {fetched_count}")
        print(f"Descrições não obtidas: {failed_count}")

        print(
            f"\n{len(sorted_jobs)} vagas analisadas salvas em: "
            f"{ANALYZED_JOBS_FILE}"
        )
        print(
            f"{len(relevant_jobs)} vagas relevantes salvas em: "
            f"{MATCHED_JOBS_FILE}"
        )
        print(
            f"{len(review_jobs)} vagas para revisão salvas em: "
            f"{REVIEW_JOBS_FILE}"
        )

        print(
            f"Vagas eliminadas antes da IA: "
            f"{hard_rejected_count}"
        )

    return {
        "jobs": sorted_jobs,
        "relevant_jobs": relevant_jobs,
        "review_jobs": review_jobs,
        "cached_descriptions": cached_count,
        "fetched_descriptions": fetched_count,
        "failed_descriptions": failed_count,
        "hard_rejected_jobs": hard_rejected_count,
    }


if __name__ == "__main__":
    main()