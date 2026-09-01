from dataclasses import dataclass

import pytest

from models.candidate_profile import CandidateProfile
from services.ai.ai_recommendation_service import (
    AIRecommendationService,
)
from services.ai.prompt_builder import (
    build_batch_prompt,
)


@dataclass
class FakeJobProfile:
    role_family: str = "Technical Support"
    summary: str = "Support role"
    seniority: str = "mid"
    must_have_capabilities: list[str] = None
    nice_to_have_capabilities: list[str] = None
    key_responsibilities: list[str] = None
    tools_and_technologies: list[str] = None
    required_qualifications: list[str] = None
    stakeholders_and_collaboration: list[str] = None
    important_details: list[str] = None
    role_context: str = ""

    def __post_init__(self):
        for field_name in (
            "must_have_capabilities",
            "nice_to_have_capabilities",
            "key_responsibilities",
            "tools_and_technologies",
            "required_qualifications",
            "stakeholders_and_collaboration",
            "important_details",
        ):
            if getattr(
                self,
                field_name,
            ) is None:
                setattr(
                    self,
                    field_name,
                    [],
                )


class FakeJob:
    def __init__(
        self,
        job_id,
        title,
    ):
        self.id = job_id
        self.title = title
        self.company = "Example"
        self.location = "Ireland"
        self.remote = True
        self.salary = ""
        self.description = (
            "Normal job description."
        )


def _items():
    return [
        (
            FakeJob(
                "job-1",
                "Support Engineer",
            ),
            FakeJobProfile(),
        ),
        (
            FakeJob(
                "job-2",
                "Technical Analyst",
            ),
            FakeJobProfile(),
        ),
    ]


def test_career_memory_appears_once_per_batch():
    memory = {
        "facts": {
            "candidate": {
                "memory_test_marker": (
                    "MEMORY_A_ONLY"
                ),
            },
        },
        "market_evidence": {
            "sample_size": 18,
        },
        "outcomes": [],
        "inferences": [],
        "hypotheses": [],
        "continuity_note": "",
    }

    prompt = build_batch_prompt(
        items=_items(),
        candidate_profile=(
            CandidateProfile()
        ),
        career_memory=memory,
    )

    # Count the actual context heading, not the
    # explanatory phrase "Within Career Memory:"
    # that appears in the safety rules.
    assert (
        prompt.count(
            "\nCareer Memory:\n\n"
        )
        == 1
    )

    # The actual candidate-specific memory payload
    # must exist only once in the entire batch.
    assert (
        prompt.count(
            "MEMORY_A_ONLY"
        )
        == 1
    )

    # Each actual job packet appears exactly once.
    # Do not count the generic job_id example in
    # the response schema later in the prompt.
    assert (
        prompt.count(
            '"job_id": "job-1"'
        )
        == 1
    )

    assert (
        prompt.count(
            '"job_id": "job-2"'
        )
        == 1
    )


def test_different_candidate_memory_does_not_leak_between_prompts():
    prompt_a = build_batch_prompt(
        items=_items(),
        candidate_profile=(
            CandidateProfile()
        ),
        career_memory={
            "continuity_note": (
                "CANDIDATE_A_PRIVATE_MEMORY"
            ),
        },
    )

    prompt_b = build_batch_prompt(
        items=_items(),
        candidate_profile=(
            CandidateProfile()
        ),
        career_memory={
            "continuity_note": (
                "CANDIDATE_B_PRIVATE_MEMORY"
            ),
        },
    )

    assert (
        "CANDIDATE_A_PRIVATE_MEMORY"
        in prompt_a
    )

    assert (
        "CANDIDATE_A_PRIVATE_MEMORY"
        not in prompt_b
    )

    assert (
        "CANDIDATE_B_PRIVATE_MEMORY"
        in prompt_b
    )

    assert (
        "CANDIDATE_B_PRIVATE_MEMORY"
        not in prompt_a
    )


def test_missing_career_memory_is_backward_compatible():
    prompt = build_batch_prompt(
        items=_items(),
        candidate_profile=(
            CandidateProfile()
        ),
    )

    assert "Career Memory:" in prompt

    # Empty object is valid context.
    assert "{}" in prompt


def test_invalid_career_memory_type_is_rejected():
    with pytest.raises(
        ValueError
    ):
        build_batch_prompt(
            items=_items(),
            candidate_profile=(
                CandidateProfile()
            ),
            career_memory=[
                "not",
                "a",
                "dict",
            ],
        )


def test_ai_service_forwards_exact_memory_to_batch_prompt(
    monkeypatch,
):
    captured = {}

    def fake_build_batch_prompt(
        *,
        items,
        candidate_profile,
        career_memory,
    ):
        captured[
            "career_memory"
        ] = career_memory

        return "fake prompt"

    def fake_parse_batch_response(
        *,
        response,
        requested_job_ids,
    ):
        captured[
            "requested_job_ids"
        ] = requested_job_ids

        return [
            "parsed"
        ]

    monkeypatch.setattr(
        (
            "services.ai."
            "ai_recommendation_service."
            "build_batch_prompt"
        ),
        fake_build_batch_prompt,
    )

    monkeypatch.setattr(
        (
            "services.ai."
            "ai_recommendation_service."
            "parse_batch_response"
        ),
        fake_parse_batch_response,
    )

    class FakeLLM:
        def generate(
            self,
            prompt,
        ):
            assert prompt == "fake prompt"
            return "fake response"

    service = AIRecommendationService(
        FakeLLM()
    )

    memory = {
        "continuity_note": (
            "EXACT_MEMORY_OBJECT"
        ),
    }

    result = service.analyze_batch(
        items=_items(),
        candidate_profile=(
            CandidateProfile()
        ),
        career_memory=memory,
    )

    assert result == [
        "parsed"
    ]

    assert (
        captured["career_memory"]
        is memory
    )

    assert (
        captured[
            "requested_job_ids"
        ]
        == [
            "job-1",
            "job-2",
        ]
    )
