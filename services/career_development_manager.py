from dataclasses import asdict

from services.ai.career_development_service import (
    CareerDevelopmentService,
)
from services.ai.openai_client import OpenAIClient
from services.career_development_context_builder import (
    build_career_development_context,
)
from services.career_development_signature import (
    build_career_development_signature,
)
from services.database import (
    get_candidate_career_development,
    save_candidate_career_development,
)


CAREER_DEVELOPMENT_VERSION = (
    "career-development-v2"
)


def get_or_generate_career_development(
    candidate_id: str,
) -> dict:
    context = (
        build_career_development_context(
            candidate_id
        )
    )

    context_signature = (
        build_career_development_signature(
            context
        )
    )

    existing = (
        get_candidate_career_development(
            candidate_id
        )
    )

    if (
        existing
        and existing.get(
            "context_signature"
        )
        == context_signature
        and existing.get(
            "analysis_version"
        )
        == CAREER_DEVELOPMENT_VERSION
    ):
        return existing.get(
            "recommendation",
            {},
        )

    service = CareerDevelopmentService(
        OpenAIClient()
    )

    recommendation = service.analyze(
        context
    )

    recommendation_dict = asdict(
        recommendation
    )

    save_candidate_career_development(
        candidate_id=candidate_id,
        context_signature=context_signature,
        recommendation=recommendation_dict,
        analysis_version=(
            CAREER_DEVELOPMENT_VERSION
        ),
    )

    return recommendation_dict
