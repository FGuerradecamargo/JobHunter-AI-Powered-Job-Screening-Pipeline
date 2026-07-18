from services.ai.llm_client import LLMClient


class FakeLLMClient(LLMClient):

    def generate(
        self,
        prompt: str,
    ) -> str:
        return """
{
  "recommendation": "apply",
  "current_fit": 80,
  "growth_value": 15,
  "strengths": [
    "technical support",
    "technical investigation"
  ],
  "gaps": [
    "limited cloud infrastructure experience"
  ],
  "reason": "Strong alignment with the candidate's support and investigation background."
}
""".strip()