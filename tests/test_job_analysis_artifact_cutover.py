import json

import pytest

from models.candidate_profile import CandidateProfile
from models.job import Job
from models.job_profile import JobProfile
from services.ai.prompt_builder import build_batch_prompt, build_prompt
from services.ai.response_parser import parse_batch_response, parse_response


def _inputs(job_id="job-1"):
    candidate = CandidateProfile(
        current_roles=["Operations Specialist"],
        bridge_roles=["Product Operations Specialist"],
        target_roles=["Product Operations Manager"],
        current_skills=["SQL", "Stakeholder communication"],
        growth_skills=["Advanced reporting"],
    )
    job = Job(
        id=job_id,
        raw_text="Product Operations Specialist at Target Ltd",
        url=f"https://example.test/{job_id}",
        title="Product Operations Specialist",
        company="Target Ltd",
        location="Dublin",
        remote=True,
        salary=None,
        easy_apply=False,
        score=None,
    )
    job.description = "Improve operational processes with SQL."
    profile = JobProfile(
        job_id=job_id,
        canonical_role="Product Operations Specialist",
        role_family="Product Operations",
        summary="Operations and reporting role.",
    )
    return candidate, job, profile


def _analysis(recommendation="best_match", **extra):
    data = {
        "recommendation": recommendation,
        "competitive_status": (
            "not_competitive_now" if recommendation == "reject" else "competitive_now"
        ),
        "current_fit": 80,
        "growth_value": 70,
        "direction_alignment": "high",
        "job_level": "Intermediate",
        "candidate_level": "Intermediate",
        "level_assessment": "Compatible levels.",
        "core_requirements": ["SQL"],
        "requirements_met": ["SQL"],
        "strengths": ["Process improvement"],
        "development_gaps": ["Advanced reporting"],
        "structural_gaps": [],
        "positive_points": ["Relevant direction"],
        "personal_negatives": [],
        "priority_matches": [],
        "priority_conflicts": [],
        "hard_conflicts": [],
        "reason": "Relevant opportunity.",
        "final_reason": "The candidate can compete.",
        "simple_summary": "The company needs operational support.",
        "simple_recommendation": "Consider applying.",
        "market_signal": {
            "role_family": "Product Operations",
            "best_match_blockers": [],
            "market_strengths": ["Process improvement"],
            "what_would_raise_fit": ["Advanced reporting"],
        },
    }
    data.update(extra)
    return data


def _single_prompt():
    candidate, job, profile = _inputs()
    return build_prompt(job, profile, candidate)


def _batch_prompt():
    candidate, job, profile = _inputs()
    return build_batch_prompt([(job, profile)], candidate)


@pytest.mark.parametrize("prompt_builder", [_single_prompt, _batch_prompt])
def test_job_analysis_prompt_has_no_tailored_cv_generation(prompt_builder):
    prompt = prompt_builder().casefold()

    assert "tailored_cv" not in prompt
    assert "tailored cv" not in prompt
    assert "source_experience_id" not in prompt
    assert "tailored_bullets" not in prompt


@pytest.mark.parametrize("prompt_builder", [_single_prompt, _batch_prompt])
def test_job_analysis_prompt_has_no_interview_generation(prompt_builder):
    prompt = prompt_builder().casefold()

    assert "interview_prep" not in prompt
    assert "interview preparation" not in prompt
    assert "likely_interview_topics" not in prompt
    assert "interview positioning" not in prompt


def test_new_approved_analysis_parses_without_application_artifacts():
    result = parse_response(json.dumps(_analysis()), "job-1")

    assert result.recommendation == "best_match"
    assert result.tailored_cv is None
    assert result.interview_prep is None


def test_reject_still_parses_without_application_artifacts():
    result = parse_response(json.dumps(_analysis("reject")), "job-1")

    assert result.recommendation == "reject"
    assert result.tailored_cv is None
    assert result.interview_prep is None


def test_legacy_tailored_cv_still_parses():
    legacy_cv = {
        "headline": "Operations Specialist",
        "professional_summary": "Experienced in process improvement.",
        "key_skills": ["SQL"],
        "experiences": [
            {
                "source_experience_id": "experience-1",
                "company": "Example Ltd",
                "role": "Operations Specialist",
                "tailored_bullets": ["Improved support processes."],
            }
        ],
        "additional_relevant_information": ["Stakeholder communication"],
    }
    result = parse_response(
        json.dumps(_analysis(tailored_cv=legacy_cv)),
        "job-1",
    )

    assert result.tailored_cv.headline == "Operations Specialist"
    assert result.tailored_cv.experiences[0].source_experience_id == "experience-1"


def test_legacy_interview_prep_still_parses():
    legacy_prep = {
        "what_the_company_needs": "Operational discipline",
        "what_you_should_demonstrate": ["Process improvement"],
        "strongest_evidence": ["Support operations"],
        "points_to_be_careful_with": ["Advanced reporting gap"],
        "likely_interview_topics": ["Stakeholder communication"],
        "positioning": "Evidence-led operator",
    }
    result = parse_response(
        json.dumps(_analysis(interview_prep=legacy_prep)),
        "job-1",
    )

    assert result.interview_prep.positioning == "Evidence-led operator"
    assert result.interview_prep.strongest_evidence == ["Support operations"]


def test_batch_analysis_without_artifacts_parses_safely():
    response = {
        "results": [{"job_id": "job-1", "analysis": _analysis()}]
    }
    result = parse_batch_response(json.dumps(response), ["job-1"])[0]

    assert result.tailored_cv is None
    assert result.interview_prep is None


@pytest.mark.parametrize(
    "recommendation",
    ["best_match", "potential", "good_opportunity", "reject"],
)
def test_recommendation_semantics_remain_supported(recommendation):
    result = parse_response(json.dumps(_analysis(recommendation)), "job-1")

    assert result.recommendation == recommendation


def test_sprint_10_market_signal_is_unchanged():
    result = parse_response(json.dumps(_analysis()), "job-1")

    assert result.market_signal.role_family == "Product Operations"
    assert result.market_signal.market_strengths == ["Process improvement"]
    assert result.market_signal.what_would_raise_fit == ["Advanced reporting"]


def test_prompt_keeps_market_and_decision_analysis_contract():
    for prompt in (_single_prompt(), _batch_prompt()):
        assert '"recommendation"' in prompt
        assert '"competitive_status"' in prompt
        assert '"market_signal"' in prompt
        assert '"structural_gaps"' in prompt
        assert '"simple_summary"' in prompt
        assert '"simple_recommendation"' in prompt
