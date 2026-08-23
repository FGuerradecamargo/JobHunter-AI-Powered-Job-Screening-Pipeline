from models.job import Job
from models.job_profile import JobProfile
from services.ai.llm_client import LLMClient
from services.ai.job_profile_prompt_builder import (
    build_job_profile_prompt,
)
from services.ai.job_profile_parser import (
    parse_job_profile,
)


class JobProfileService:

    def __init__(
        self,
        llm_client: LLMClient,
    ) -> None:
        self.llm_client = llm_client

    def create(
        self,
        job: Job,
    ) -> JobProfile:
        prompt = build_job_profile_prompt(job)

        raw_response = self.llm_client.generate(
            prompt
        )

        return parse_job_profile(
            response=raw_response,
            job_id=job.id,
        )
