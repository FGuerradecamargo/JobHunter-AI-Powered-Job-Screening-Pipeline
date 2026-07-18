import os

from dotenv import load_dotenv
from openai import OpenAI

from services.ai.llm_client import LLMClient


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
        )

    def generate(
        self,
        prompt: str,
    ) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )

        return response.output_text