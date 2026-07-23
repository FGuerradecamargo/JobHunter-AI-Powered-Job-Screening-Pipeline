from openai import RateLimitError
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from models.job import Job
from services.ai.ai_recommendation_service import (
    AIRecommendationService,
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


def load_ai_cache() -> list[dict]:
    if not AI_RECOMMENDED_JOBS_FILE.exists():
        return []

    try:
        data = json.loads(
            AI_RECOMMENDED_JOBS_FILE.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    return data


def save_ai_cache(
    recommendations: list[dict],
) -> None:
    recommendations.sort(
        key=lambda item: str(
            item.get("job", {}).get("id", "")
        )
    )

    AI_RECOMMENDED_JOBS_FILE.write_text(
        json.dumps(
            recommendations,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def build_job_signature(
    job_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Fields that require a new AI analysis when changed.
    """
    return {
        "id": job_data.get("id"),
        "title": job_data.get("title"),
        "company": job_data.get("company"),
        "location": job_data.get("location"),
        "remote": job_data.get("remote"),
        "salary": job_data.get("salary"),
        "description": job_data.get("description"),
        "url": job_data.get("url"),
    }


def cache_is_current(
    job: Job,
    cached_item: dict,
) -> bool:
    cached_job = cached_item.get("job")

    if not isinstance(cached_job, dict):
        return False

    current_job = asdict(job)

    return (
        build_job_signature(current_job)
        == build_job_signature(cached_job)
    )


def serialize_recommendation(
    job: Job,
    analysis,
) -> dict:
    return {
        "job": asdict(job),
        "analysis": asdict(analysis),
    }


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

    cached_recommendations = load_ai_cache()

    cache_by_job_id = {
        str(item["job"]["id"]): item
        for item in cached_recommendations
        if isinstance(item.get("job"), dict)
        and item["job"].get("id") is not None
    }

    llm_client = OpenAIClient()

    recommendation_service = AIRecommendationService(
        llm_client
    )

    current_results: list[dict] = []
    pending_jobs: list[Job] = []

    reused_count = 0
    analyzed_count = 0
    quota_interrupted = False

    total = len(selected_jobs)

    # Primeiro recupera todo o cache disponível.
    # Isso acontece antes de qualquer chamada à API.
    for job in selected_jobs:
        job_id = str(job.id)
        cached_item = cache_by_job_id.get(job_id)

        if (
                cached_item is not None
                and cache_is_current(job, cached_item)
        ):
            current_results.append(cached_item)
            reused_count += 1
        else:
            pending_jobs.append(job)

    if verbose:
        print(
            f"Análises reutilizadas do cache: "
            f"{reused_count}"
        )
        print(
            f"Vagas aguardando análise de IA: "
            f"{len(pending_jobs)}"
        )

    # Agora chama a API somente para vagas novas ou alteradas.
    for index, job in enumerate(
            pending_jobs,
            start=1,
    ):
        if verbose:
            print(
                f"[{index}/{len(pending_jobs)}] "
                f"Analisando: {job.title}"
            )

        try:
            analysis = recommendation_service.analyze(
                job=job,
                candidate_profile=profile,
            )

        except RateLimitError as error:
            quota_interrupted = True

            print()
            print("=" * 60)
            print("QUOTA DA API INDISPONÍVEL")
            print("=" * 60)
            print(
                "As análises já armazenadas serão reutilizadas."
            )
            print(
                f"Vagas ainda sem análise: "
                f"{len(pending_jobs) - index + 1}"
            )
            print("=" * 60)

            break

        serialized_item = serialize_recommendation(
            job,
            analysis,
        )

        current_results.append(serialized_item)
        cache_by_job_id[str(job.id)] = serialized_item
        analyzed_count += 1

        # Salva depois de cada chamada bem-sucedida.
        save_ai_cache(
            list(cache_by_job_id.values())
        )

    # Preserva também análises históricas que não estejam
    # no conjunto relevante desta execução.
    save_ai_cache(
        list(cache_by_job_id.values())
    )

    if verbose:
        print()
        print("=" * 60)
        print("ANÁLISE DE IA")
        print("=" * 60)
        print(
            f"Vagas selecionadas:       {total}"
        )
        print(
            f"Análises reutilizadas:    {reused_count}"
        )
        print(
            f"Novas análises de IA:     {analyzed_count}"
        )
        print(
            f"Resultados desta execução: "
            f"{len(current_results)}"
        )
        print("=" * 60)

        print(
            f"Interrompido por quota:   "
            f"{'sim' if quota_interrupted else 'não'}"
        )

    return current_results


if __name__ == "__main__":
    main()