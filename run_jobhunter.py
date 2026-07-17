import argparse
import sys

import analyze_jobs
import main as collect_jobs
import recommend_jobs


# =========================
# Defaults
# =========================

DEFAULT_VERBOSE = False
DEFAULT_FILTER = "relevant"
DEFAULT_LIMIT = 10


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the complete JobHunter pipeline."
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=DEFAULT_VERBOSE,
        help="Show detailed job listings."
    )

    parser.add_argument(
        "--filter",
        choices=[
            "all",
            "relevant",
            "review",
            "not_relevant",
        ],
        default=DEFAULT_FILTER,
        help="Which analyzed jobs should be displayed."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of jobs to display."
    )

    return parser.parse_args()


def print_job(job) -> None:
    print(f"Título: {job.title}")
    print(f"Empresa: {job.company}")
    print(f"Localização: {job.location}")
    print(f"Score: {job.score}")
    print(f"Classificação: {job.classification}")
    print(f"URL: {job.url}")
    print("-" * 60)


def print_filtered_jobs(
    analysis_result: dict,
    filter_by: str,
    limit: int | None,
) -> None:
    jobs = analysis_result["jobs"]

    if filter_by == "relevant":
        filtered_jobs = analysis_result["relevant_jobs"]

    elif filter_by == "review":
        filtered_jobs = analysis_result["review_jobs"]

    elif filter_by == "not_relevant":
        filtered_jobs = [
            job
            for job in jobs
            if job.classification == "not_relevant"
        ]

    else:
        filtered_jobs = jobs

    if limit is not None:
        filtered_jobs = filtered_jobs[:limit]

    if limit is not None:
        filtered_jobs = filtered_jobs[:limit]

    if not filtered_jobs:
        print("\nNenhuma vaga para exibir.")
        return

    print("\n" + "=" * 60)
    print(f"EXIBINDO: {filter_by.upper()}")
    print("=" * 60)

    for job in filtered_jobs:
        print_job(job)


def print_summary(
    collection_result: dict,
    analysis_result: dict,
    recommendations: list[dict],
) -> None:

    total_collected = len(collection_result["jobs"])
    total_analyzed = len(analysis_result["jobs"])
    total_relevant = len(analysis_result["relevant_jobs"])
    total_review = len(analysis_result["review_jobs"])

    total_not_relevant = (
        total_analyzed
        - total_relevant
        - total_review
    )

    print("\n" + "=" * 60)
    print("JOBHUNTER — RESUMO FINAL")
    print("=" * 60)

    print(f"Vagas coletadas:       {total_collected}")
    print(f"Vagas analisadas:      {total_analyzed}")
    print(f"Vagas relevantes:      {total_relevant}")
    print(f"Vagas para revisão:    {total_review}")
    print(f"Vagas não relevantes:  {total_not_relevant}")
    print(f"Recomendações geradas: {len(recommendations)}")

    print("=" * 60)


def main() -> None:

    args = parse_arguments()

    print("=" * 60)
    print("JOBHUNTER — PIPELINE")
    print("=" * 60)

    try:
        collection_result = collect_jobs.main(
            verbose=False,
        )

        analysis_result = analyze_jobs.main(
            verbose=False,
        )

        recommendations = recommend_jobs.main(
            verbose=False,
        )

        print_summary(
            collection_result=collection_result,
            analysis_result=analysis_result,
            recommendations=recommendations,
        )

        if args.verbose:
            print_filtered_jobs(
                analysis_result=analysis_result,
                filter_by=args.filter,
                limit=args.limit,
            )

    except Exception as error:
        print("\n" + "=" * 60)
        print("PIPELINE INTERROMPIDO")
        print("=" * 60)
        print(error)
        print("=" * 60)

        sys.exit(1)


if __name__ == "__main__":
    main()
