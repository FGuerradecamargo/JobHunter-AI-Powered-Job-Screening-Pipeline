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
)
from services.market_position_service import (
    build_market_position,
)


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

    market_position = build_market_position(
        candidate_id=candidate_id,
        batch_signals=[],
    )

    historical_market = (
        market_position.get(
            "historical",
            {},
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

        analyzed_jobs_count=(
            historical_market.get(
                "sample_size",
                0,
            )
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

        market_role_families=(
            historical_market.get(
                "role_families",
                [],
            )
        ),

        market_strengths=(
            historical_market.get(
                "market_strengths",
                [],
            )
        ),

        market_blockers=(
            historical_market.get(
                "best_match_blockers",
                [],
            )
        ),

        market_fit_opportunities=(
            historical_market.get(
                "what_would_raise_fit",
                [],
            )
        ),

        application_outcomes=outcomes,
    )
