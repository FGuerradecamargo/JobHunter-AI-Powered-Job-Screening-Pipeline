from services.ai.llm_client import LLMClient


class FakeLLMClient(LLMClient):

    def generate(
        self,
        prompt: str,
    ) -> str:
        return """
{
  "recommendation": "best_match",
  "competitive_status": "competitive_now",
  "current_fit": 82,
  "growth_value": 78,
  "direction_alignment": "high",
  "job_level": "Intermediate technical support role",
  "candidate_level": "Experienced operations and support professional",
  "level_assessment": "The levels are compatible.",
  "core_requirements": [
    "technical troubleshooting",
    "incident investigation"
  ],
  "requirements_met": [
    "technical troubleshooting",
    "incident investigation"
  ],
  "strengths": [
    "root cause analysis",
    "technical investigations"
  ],
  "development_gaps": [
    "Linux administration"
  ],
  "structural_gaps": [],
  "positive_points": [
    "strong career progression"
  ],
  "personal_negatives": [],
  "priority_matches": [],
  "priority_conflicts": [],
  "hard_conflicts": [],
  "reason": "The role matches the candidate's experience.",
  "final_reason": "The candidate can compete for this role.",
  "simple_summary": "The role focuses on support and investigation.",
  "simple_recommendation": "Apply.",
  "market_signal": {
    "role_family": "Technical Support",
    "best_match_blockers": [],
    "market_strengths": [
      "Technical investigation"
    ],
    "what_would_raise_fit": []
  },
  "tailored_cv": null,
  "interview_prep": null
}
""".strip()
