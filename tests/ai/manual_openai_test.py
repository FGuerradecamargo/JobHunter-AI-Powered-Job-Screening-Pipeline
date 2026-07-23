import json

from models.candidate_profile import CandidateProfile
from models.job import Job
from services.ai.ai_recommendation_service import (
    AIRecommendationService,
)
from services.ai.openai_client import OpenAIClient


def main() -> None:
    with open(
        "candidate_profile.json",
        "r",
        encoding="utf-8",
    ) as file:
        profile_data = json.load(file)

    candidate_profile = CandidateProfile(
        **profile_data
    )

    job = Job(
        id="manual-test",
        raw_text="Manual test",
        url="https://example.com",
        title="Technical Support Engineer",
        company="Example Company",
        location="Ireland",
        remote=True,
        salary=None,
        easy_apply=False,
        score=None,
    )

    job.description = """
    Technical support, troubleshooting,
    APIs, logs and customer escalations.
    """.strip()

    service = AIRecommendationService(
        llm_client=OpenAIClient(),
    )

    result = service.analyze(
        job=job,
        candidate_profile=candidate_profile,
    )

    print(result)


if __name__ == "__main__":
    main()