import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from services.ai.llm_client import LLMClient
from services.provider_failure import provider_operation


class OpenAIClient(LLMClient):

    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY was not found in the environment."
            )

        self.model = model or os.getenv(
            "OPENAI_MODEL",
            "gpt-5.5",
        )

        self.client = OpenAI(
            api_key=api_key,
            timeout=120.0,
            max_retries=0,
        )

    @provider_operation(
        "ai_generation"
    )
    def generate_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
    ) -> dict:
        """
        Ask the provider to enforce the response shape.

        This does not replace WorkPilot's domain validator:
        provider structure and domain authority are separate
        boundaries.
        """
        response = self.client.responses.parse(
            model=self.model,
            input=prompt,
            text_format=response_model,
        )

        parsed = response.output_parsed

        if parsed is None:
            raise ValueError(
                "Structured model output "
                "was not available."
            )

        return parsed.model_dump(
            mode="json"
        )

    @provider_operation('ai_generation')
    def generate(
        self,
        prompt: str,
    ) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )

        return response.output_text
