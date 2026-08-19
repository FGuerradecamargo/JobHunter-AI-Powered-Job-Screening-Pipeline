from models.career_development_context import (
    CareerDevelopmentContext,
)
from models.career_development_recommendation import (
    CareerDevelopmentRecommendation,
)
from services.ai.career_development_parser import (
    parse_career_development_response,
)
from services.ai.career_development_prompt_builder import (
    build_career_development_prompt,
)
from services.ai.llm_client import LLMClient


class CareerDevelopmentService:

    def __init__(
        self,
        llm_client: LLMClient,
    ) -> None:
        self.llm_client = llm_client

    def analyze(
        self,
        context: CareerDevelopmentContext,
    ) -> CareerDevelopmentRecommendation:
        prompt = build_career_development_prompt(
            context
        )

        raw_response = (
            self.llm_client.generate(
                prompt
            )
        )

        return parse_career_development_response(
            raw_response
        )
