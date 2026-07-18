import json

from models.candidate_profile import CandidateProfile
from models.job import Job
from services.ai.ai_recommendation_service import AIRecommendationService
from services.ai.fake_llm_client import FakeLLMClient


with open(
    "candidate_profile.json",
    "r",
    encoding="utf-8",
) as file:
    profile_data = json.load(file)


candidate_profile = CandidateProfile(
    **profile_data,
)

job = Job(
    id="test-001",
    raw_text="Technical Support Engineer",
    url="https://example.com/job/test-001",
    title="Technical Support Engineer",
    company="Example Company",
    location="Dublin, Ireland",
    remote=False,
    salary=None,
    easy_apply=False,
    score=55,
)

job.description = """
Investigate technical issues, support customers,
work with APIs, Linux systems and incident management.
""".strip()


service = AIRecommendationService(
    llm_client=FakeLLMClient(),
)

recommendation = service.analyze(
    job=job,
    candidate_profile=candidate_profile,
)

print(recommendation)