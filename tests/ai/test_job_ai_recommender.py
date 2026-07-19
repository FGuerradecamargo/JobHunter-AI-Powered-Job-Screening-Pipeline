from models.candidate_profile import CandidateProfile
from models.job import Job
from services.ai.ai_recommendation_service import AIRecommendationService
from services.ai.fake_llm_client import FakeLLMClient
from services.ai.job_ai_recommender import JobAIRecommender


def test_recommends_multiple_jobs():
    jobs = [
        Job(
            id="job-1",
            raw_text="Support Engineer at Company A",
            url="https://example.com/job-1",
            title="Support Engineer",
            company="Company A",
            location="Limerick",
            remote=False,
            salary=None,
            easy_apply=False,
            score=None,
        ),
        Job(
            id="job-2",
            raw_text="Technical Analyst at Company B",
            url="https://example.com/job-2",
            title="Technical Analyst",
            company="Company B",
            location="Dublin",
            remote=True,
            salary=None,
            easy_apply=False,
            score=None,
        ),
    ]

    candidate_profile = CandidateProfile(
        current_roles=["Customer Service Specialist"],
        bridge_roles=["Technical Support"],
        target_roles=["Technical Operations"],
        current_skills=["Troubleshooting"],
        growth_skills=["Python"],
    )

    llm_client = FakeLLMClient()
    recommendation_service = AIRecommendationService(llm_client)
    recommender = JobAIRecommender(recommendation_service)

    recommendations = recommender.recommend(
        jobs,
        candidate_profile,
    )

    assert len(recommendations) == 2

    assert recommendations[0].job == jobs[0]
    assert recommendations[1].job == jobs[1]

    assert recommendations[0].analysis.recommendation == "apply"
    assert recommendations[1].analysis.recommendation == "apply"