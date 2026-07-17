import json
from pathlib import Path

from models.job import Job
from services.analyzers.candidate_fit_analyzer import (
    CandidateFitAnalyzer,
)
from services.candidate_profile_loader import (
    load_candidate_profile,
)
from services.recommenders.recommendation_engine import (
    RecommendationEngine,
)


BASE_DIR = Path(__file__).resolve().parent

MATCHED_JOBS_FILE = BASE_DIR / "jobs_matched.json"
CANDIDATE_PROFILE_FILE = BASE_DIR / "candidate_profile.json"
RECOMMENDED_JOBS_FILE = BASE_DIR / "jobs_recommended.json"


def load_matched_jobs() -> list[Job]:
    if not MATCHED_JOBS_FILE.exists():
        raise FileNotFoundError(
            "jobs_matched.json não encontrado. "
            "Execute primeiro: python analyze_jobs.py"
        )

    jobs_data = json.loads(
        MATCHED_JOBS_FILE.read_text(encoding="utf-8")
    )

    return [
        Job(**job_data)
        for job_data in jobs_data
    ]


def build_recommendation(
    job: Job,
    fit_analysis: dict,
    decision: dict,
) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "remote": job.remote,
        "easy_apply": job.easy_apply,
        "url": job.url,
        "job_score": job.score,
        "job_classification": job.classification,
        "current_fit": fit_analysis["current_fit"],
        "growth_value": fit_analysis["growth_value"],
        "current_fit_reasons": fit_analysis[
            "current_fit_reasons"
        ],
        "growth_reasons": fit_analysis[
            "growth_reasons"
        ],
        "recommendation": decision["recommendation"],
        "recommendation_message": decision["message"],
    }


def main(
    verbose: bool = True,
) -> list[dict]:
    jobs = load_matched_jobs()

    profile = load_candidate_profile(
        CANDIDATE_PROFILE_FILE
    )

    fit_analyzer = CandidateFitAnalyzer()
    recommendation_engine = RecommendationEngine()

    recommendations = []

    for job in jobs:
        fit_analysis = fit_analyzer.analyze(
            job,
            profile,
        )

        decision = recommendation_engine.recommend(
            current_fit=fit_analysis["current_fit"],
            growth_value=fit_analysis["growth_value"],
        )

        recommendation = build_recommendation(
            job,
            fit_analysis,
            decision,
        )

        recommendations.append(recommendation)

    recommendations.sort(
        key=lambda item: (
            item["current_fit"],
            item["growth_value"],
            item["job_score"] or 0,
        ),
        reverse=True,
    )

    RECOMMENDED_JOBS_FILE.write_text(
        json.dumps(
            recommendations,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if verbose:
        for recommendation in recommendations:
            print(recommendation["title"])
            print(f"Empresa: {recommendation['company']}")
            print(
                f"Current fit: "
                f"{recommendation['current_fit']}"
            )
            print(
                f"Growth value: "
                f"{recommendation['growth_value']}"
            )
            print(
                f"Recomendação: "
                f"{recommendation['recommendation']}"
            )
            print(
                recommendation["recommendation_message"]
            )
            print("-" * 60)

        print(
            f"{len(recommendations)} recomendações salvas em: "
            f"{RECOMMENDED_JOBS_FILE}"
        )

    return recommendations


if __name__ == "__main__":
    main()