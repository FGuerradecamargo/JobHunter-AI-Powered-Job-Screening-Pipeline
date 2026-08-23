from models.ai_recommendation import AIRecommendation
from models.candidate_profile import CandidateProfile
from models.job import Job
from models.job_profile import JobProfile
from services.ai.llm_client import LLMClient
from services.ai.prompt_builder import build_prompt
from services.ai.response_parser import parse_response


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
