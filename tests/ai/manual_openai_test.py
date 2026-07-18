from models.candidate_profile import CandidateProfile
from models.job import Job
from services.ai.ai_recommendation_service import AIRecommendationService
from services.ai.openai_client import OpenAIClient


candidate_profile = CandidateProfile(
    current_roles=[
        "Technical Support Engineer",
    ],
    bridge_roles=[
        "Technical Operations Analyst",
    ],
    target_roles=[
        "Technical Investigations Specialist",
    ],
    current_skills=[
        "Python",
        "Linux",
        "Technical Support",
        "Troubleshooting",
    ],
    growth_skills=[
        "Cloud Infrastructure",
        "SQL",
        "Workflow Automation",
    ],
)

job = Job(
    id="manual-test-001",
    raw_text="Technical Operations Analyst at Example Company",
    url="https://example.com/job",
    title="Technical Operations Analyst",
    company="Example Company",
    location="Dublin",
    remote=False,
    salary=None,
    easy_apply=False,
    score=None,
)

job.description = """
Investigate technical incidents, troubleshoot customer issues,
analyze logs, work with Linux systems, SQL and internal APIs,
and collaborate with engineering teams.
""".strip()

service = AIRecommendationService(
    llm_client=OpenAIClient(),
)

result = service.analyze(
    job=job,
    candidate_profile=candidate_profile,
)

print(result)