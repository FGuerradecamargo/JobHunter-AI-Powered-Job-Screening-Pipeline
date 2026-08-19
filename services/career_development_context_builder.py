from collections import Counter

from models.career_development_context import (
    CareerDevelopmentContext,
)
from services.career_objective_repository import (
    CareerObjectiveRepository,
)
from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.database import (
    count_candidate_jobs_by_status,
    list_candidate_application_outcomes,
    list_candidate_jobs,
)


def _normalize_items(
    items: list[str],
) -> list[str]:
    normalized = []

    for item in items:
        value = str(item).strip()

        if value:
            normalized.append(value)

    return normalized


def _rank_recurring(
    values: list[str],
) -> list[dict]:
    counter = Counter(
        value.casefold()
        for value in values
        if value.strip()
    )

    canonical = {}

    for value in values:
        clean = value.strip()

        if clean:
            canonical.setdefault(
                clean.casefold(),
                clean,
            )

    ranked = []

    for normalized, count in counter.most_common():
        ranked.append(
            {
                "text": canonical[normalized],
                "count": count,
            }
        )

    return ranked


def build_career_development_context(
    candidate_id: str,
) -> CareerDevelopmentContext:
    objective_repository = (
        CareerObjectiveRepository()
    )

    update_repository = (
        CareerUpdateRepository()
    )

    objective = (
        objective_repository.get_active(
            candidate_id
        )
    )

    career_updates = (
        update_repository.list_for_candidate(
            candidate_id
        )
    )

    statuses = (
        count_candidate_jobs_by_status(
            candidate_id
        )
    )

    analysis_statuses = [
        "in_review",
        "applied",
        "rejected_before_interview",
        "in_process",
        "rejected_after_interview",
        "offer",
    ]

    analyzed_jobs = []

    for status in analysis_statuses:
        analyzed_jobs.extend(
            list_candidate_jobs(
                candidate_id=candidate_id,
                status=status,
            )
        )

    development_gaps = []
    structural_gaps = []
    requirements_met = []

    for job in analyzed_jobs:
        analysis = job.get(
            "analysis",
            {},
        )

        development_gaps.extend(
            _normalize_items(
                analysis.get(
                    "development_gaps",
                    [],
                )
            )
        )

        structural_gaps.extend(
            _normalize_items(
                analysis.get(
                    "structural_gaps",
                    [],
                )
            )
        )

        requirements_met.extend(
            _normalize_items(
                analysis.get(
                    "requirements_met",
                    [],
                )
            )
        )

    outcomes = (
        list_candidate_application_outcomes(
            candidate_id
        )
    )

    return CareerDevelopmentContext(
        candidate_id=candidate_id,

        career_objective_title=(
            objective.title
            if objective
            else ""
        ),

        career_objective_description=(
            objective.description
            if objective
            else ""
        ),

        career_updates=[
            (
                update.update_type
                + ": "
                + update.description
            )
            for update in career_updates
        ],

        analyzed_jobs_count=len(
            analyzed_jobs
        ),

        applied_jobs_count=statuses.get(
            "applied",
            0,
        ),

        interview_process_count=statuses.get(
            "in_process",
            0,
        ),

        rejected_before_interview_count=(
            statuses.get(
                "rejected_before_interview",
                0,
            )
        ),

        rejected_after_interview_count=(
            statuses.get(
                "rejected_after_interview",
                0,
            )
        ),

        offers_count=statuses.get(
            "offer",
            0,
        ),

        recurring_development_gaps=(
            _rank_recurring(
                development_gaps
            )
        ),

        recurring_structural_gaps=(
            _rank_recurring(
                structural_gaps
            )
        ),

        recurring_requirements_met=(
            _rank_recurring(
                requirements_met
            )
        ),

        application_outcomes=outcomes,
    )
