import json
from dataclasses import asdict
from pathlib import Path

from models.job import Job
from services.ai.ai_recommendation_service import (
    AIRecommendationService,
)
from services.ai.job_ai_recommender import (
    JobAIRecommender,
)
from services.ai.openai_client import OpenAIClient
from services.candidate_profile_loader import (
    load_candidate_profile,
)


BASE_DIR = Path(__file__).resolve().parent

MATCHED_JOBS_FILE = BASE_DIR / "jobs_matched.json"
RECOMMENDED_JOBS_FILE = BASE_DIR / "jobs_recommended.json"
CANDIDATE_PROFILE_FILE = BASE_DIR / "candidate_profile.json"
AI_RECOMMENDED_JOBS_FILE = (
    BASE_DIR / "jobs_ai_recommended.json"
)


def load_matched_jobs() -> list[Job]:
    if not MATCHED_JOBS_FILE.exists():
        raise FileNotFoundError(
            "jobs_matched.json não encontrado. "
            "Execute primeiro: python analyze_jobs.py"
        )

    jobs_data = json.loads(
        MATCHED_JOBS_FILE.read_text(
            encoding="utf-8"
        )
    )

    return [
        Job(**job_data)
        for job_data in jobs_data
    ]


def load_recommended_job_ids() -> set[str]:
    if not RECOMMENDED_JOBS_FILE.exists():
        raise FileNotFoundError(
            "jobs_recommended.json não encontrado. "
            "Execute primeiro: python recommend_jobs.py"
        )

    recommendations = json.loads(
        RECOMMENDED_JOBS_FILE.read_text(
            encoding="utf-8"
        )
    )

    return {
        recommendation["id"]
        for recommendation in recommendations
    }


def select_recommended_jobs(
    jobs: list[Job],
    recommended_ids: set[str],
) -> list[Job]:
    return [
        job
        for job in jobs
        if job.id in recommended_ids
    ]


def serialize_recommendations(
    recommendations,
) -> list[dict]:
    return [
        {
            "job": asdict(item.job),
            "analysis": asdict(item.analysis),
        }
        for item in recommendations
    ]


def main(
    verbose: bool = True,
) -> list[dict]:
    jobs = load_matched_jobs()

    recommended_ids = load_recommended_job_ids()

    selected_jobs = select_recommended_jobs(
        jobs,
        recommended_ids,
    )

    profile = load_candidate_profile(
        CANDIDATE_PROFILE_FILE
    )

    llm_client = OpenAIClient()

    recommendation_service = AIRecommendationService(
        llm_client
    )

    recommender = JobAIRecommender(
        recommendation_service
    )

    recommendations = recommender.recommend(
        selected_jobs,
        profile,
    )

    serialized = serialize_recommendations(
        recommendations
    )

    serialized.sort(
        key=lambda item: (
            item["analysis"]["current_fit"],
            item["analysis"]["growth_value"],
        ),
        reverse=True,
    )

    AI_RECOMMENDED_JOBS_FILE.write_text(
        json.dumps(
            serialized,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if verbose:
        for index, item in enumerate(
            serialized,
            start=1,
        ):
            job = item["job"]
            analysis = item["analysis"]

            print(
                f"[{index}/{len(serialized)}] "
                f"{job['title']}"
            )
            print(
                f"Empresa: {job['company']}"
            )
            print(
                f"Recomendação: "
                f"{analysis['recommendation']}"
            )
            print(
                f"Current fit: "
                f"{analysis['current_fit']}"
            )
            print(
                f"Growth value: "
                f"{analysis['growth_value']}"
            )
            print("-" * 60)

        print(
            f"{len(serialized)} análises salvas em "
            f"{AI_RECOMMENDED_JOBS_FILE}"
        )

    return serialized


if __name__ == "__main__":
    main()