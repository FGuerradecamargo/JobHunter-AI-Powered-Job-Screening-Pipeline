from models.candidate_profile import CandidateProfile
from models.job import Job
from services.ai.prompt_builder import build_prompt


def test_build_prompt_contains_job_and_candidate_information():
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
        ],
        growth_skills=[
            "Cloud Infrastructure",
            "SQL",
        ],
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

    prompt = build_prompt(
        job=job,
        candidate_profile=candidate_profile,
    )

    assert "Technical Support Engineer" in prompt
    assert "Example Company" in prompt
    assert "Linux" in prompt
    assert "Technical Operations Analyst" in prompt
    assert "Cloud Infrastructure" in prompt