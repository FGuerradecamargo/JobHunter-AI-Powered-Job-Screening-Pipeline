from pathlib import Path

from services.candidate_profile_output_schema import (
    CandidateProfileOutput,
)


def test_candidate_profile_provider_schema_is_closed():
    schema = (
        CandidateProfileOutput
        .model_json_schema()
    )

    assert (
        schema[
            "additionalProperties"
        ]
        is False
    )


def test_candidate_generation_keeps_domain_validation_after_provider_schema():
    source = Path(
        "services/candidate_profile_generation_service.py"
    ).read_text(
        encoding="utf-8"
    )

    structured = source.index(
        "generate_structured"
    )

    domain_validation = (
        source.index(
            "validate_output(",
            structured,
        )
    )

    assert (
        structured
        < domain_validation
    )


def test_openai_transport_uses_responses_parse():
    source = Path(
        "services/ai/openai_client.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "self.client.responses.parse("
        in source
    )

    assert (
        "text_format=response_model"
        in source
    )
