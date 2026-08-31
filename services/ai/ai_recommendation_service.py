from models.ai_recommendation import AIRecommendation
from models.candidate_profile import CandidateProfile
from models.job import Job
from models.job_profile import JobProfile
from services.ai.llm_client import LLMClient
from services.ai.prompt_builder import (
    BATCH_MAX_SIZE,
    build_batch_prompt,
    build_prompt,
)
from services.ai.response_parser import (
    parse_batch_response,
    parse_response,
)


class AIRecommendationService:

    def __init__(
        self,
        llm_client: LLMClient,
    ) -> None:
        self.llm_client = llm_client

    def analyze(
        self,
        job: Job,
        job_profile: JobProfile,
        candidate_profile: CandidateProfile,
    ) -> AIRecommendation:

        prompt = build_prompt(
            job=job,
            job_profile=job_profile,
            candidate_profile=candidate_profile,
        )

        raw_response = self.llm_client.generate(prompt)

        return parse_response(
            response=raw_response,
            job_id=job.id,
        )

    def analyze_batch(
        self,
        items: list[tuple[Job, JobProfile]],
        candidate_profile: CandidateProfile,
    ) -> list[AIRecommendation]:
        """
        Analyze up to BATCH_MAX_SIZE jobs in one LLM
        request while preserving independent job results.
        """
        if not items:
            raise ValueError(
                "Batch must contain at least one job."
            )

        if len(items) > BATCH_MAX_SIZE:
            raise ValueError(
                f"Batch cannot contain more than "
                f"{BATCH_MAX_SIZE} jobs."
            )

        requested_job_ids = [
            str(job.id)
            for job, _ in items
        ]

        if (
            len(requested_job_ids)
            != len(set(requested_job_ids))
        ):
            raise ValueError(
                "Batch contains duplicate job IDs."
            )

        prompt = build_batch_prompt(
            items=items,
            candidate_profile=candidate_profile,
        )

        raw_response = self.llm_client.generate(
            prompt
        )

        return parse_batch_response(
            response=raw_response,
            requested_job_ids=requested_job_ids,
        )

