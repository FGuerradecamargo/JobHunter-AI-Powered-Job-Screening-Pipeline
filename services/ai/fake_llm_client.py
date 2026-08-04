from services.ai.llm_client import LLMClient


class FakeLLMClient(LLMClient):

    def generate(
        self,
        prompt: str,
    ) -> str:
        return """
{
  "recommendation": "recommended_apply",
  "competitive_status": "competitive_now",
  "current_fit": 82,
  "growth_value": 78,
  "job_level": "Intermediate technical support role",
  "candidate_level": "Experienced operations and support professional transitioning into technical support",
  "level_assessment": "The role is compatible with the candidate's current level and provides a realistic technical transition.",
  "core_requirements": [
    "technical troubleshooting",
    "incident investigation",
    "clear technical communication"
  ],
  "requirements_met": [
    "technical troubleshooting",
    "incident investigation",
    "clear technical communication"
  ],
  "strengths": [
    "root cause analysis",
    "technical investigations",
    "Python automation"
  ],
  "development_gaps": [
    "Linux administration",
    "cloud platform experience"
  ],
  "structural_gaps": [],
  "positive_points": [
    "strong career progression",
    "technical investigation work"
  ],
  "personal_negatives": [
    "Dublin location may require relocation"
  ],
  "hard_conflicts": [],
  "reason": "The role uses the candidate's investigation and troubleshooting experience while providing realistic technical growth.",
  "final_reason": "The candidate can compete for this role and the remaining gaps are suitable for preparation or onboarding."
  
  "simple_summary": (
    "The company is looking for someone who can support its "
    "systems, investigate problems and work with different teams "
    "to keep services running. You already bring investigation, "
    "support and process-improvement experience. What is less clear "
    "is your direct experience with some of the role's technical tools."
),
"simple_recommendation": (
    "Apply. Your background matches the central work, and the "
    "remaining gaps appear manageable."
),

}
""".strip()