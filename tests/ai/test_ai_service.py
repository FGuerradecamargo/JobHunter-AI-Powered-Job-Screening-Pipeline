from models.candidate_profile import CandidateProfile
from models.job import Job
from services.ai.ai_recommendation_service import AIRecommendationService
from services.ai.fake_llm_client import FakeLLMClient


def test_ai_recommendation_service_returns_recommendation():
    candidate_profile = CandidateProfile(
        current_roles=["Technical Support Engineer"],
        bridge_roles=["Technical Operations Analyst"],
        target_roles=["Technical Investigations Specialist"],
        current_skills=["Python", "Linux", "Technical Support"],
        growth_skills=["Cloud Infrastructure", "SQL"],
    )

    job = Job(
        id="test-001",
        raw_text="Technical Support Engineer at Example Company",
        url="https://example.com/job",
        title="Technical Support Engineer",
        company="Example Company",
        location="Dublin",
        remote=False,
        salary=None,
        easy_apply=False,
        score=None,
    )

    job.description = (
        "Support customers, investigate incidents "
        "and troubleshoot Linux systems."
    )

    service = AIRecommendationService(
        llm_client=FakeLLMClient(),
    )

    result = service.analyze(
        job=job,
        candidate_profile=candidate_profile,
    )

    assert result.job_id == "test-001"
    assert result.recommendation == "recommended_apply"
    assert result.competitive_status == "competitive_now"
    assert result.current_fit == 82
    assert result.growth_value == 78