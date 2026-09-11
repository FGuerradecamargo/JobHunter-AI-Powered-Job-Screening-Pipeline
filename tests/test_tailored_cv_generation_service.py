import json
from dataclasses import asdict, replace

import pytest

from models.application_context import ApplicationContext, PositioningTheme
from models.application_contract import ApplicationEvidenceRef
from services.tailored_cv_generation_request_builder import (
    build_tailored_cv_generation_request,
)
from services.tailored_cv_generation_service import TailoredCVGenerationService


def _evidence(ref, source_type, source_id, authority, statement):
    return ApplicationEvidenceRef(
        evidence_ref=ref,
        source_type=source_type,
        source_id=source_id,
        authority=authority,
        statement=statement,
    )


def _context():
    direct = _evidence(
        "e-direct",
        "professional_experience",
        "experience-1",
        "professional_fact",
        "Managed support escalations",
    )
    transferable = _evidence(
        "e-transferable",
        "transferable_capability",
        "candidate:transferable",
        "transferable_evidence",
        "Stakeholder communication",
    )
    skill = _evidence(
        "e-skill",
        "skill",
        "candidate:skills",
        "candidate_profile_fact",
        "SQL",
    )
    developing = _evidence(
        "e-developing",
        "developing_capability",
        "candidate:developing",
        "developing_evidence",
        "Kubernetes fundamentals",
    )
    unrelated = _evidence(
        "e-unrelated",
        "technical_tool",
        "candidate:tools",
        "candidate_profile_fact",
        "Private unrelated tool",
    )
    return ApplicationContext(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        contract_signature="contract-signature",
        job_title="Product Operations Specialist",
        company="Target Ltd",
        role_family="Product Operations",
        job_level="Intermediate",
        core_requirements=["SQL"],
        direct_evidence=[direct],
        transferable_evidence=[transferable],
        supporting_evidence=[skill],
        developing_evidence=[developing],
        available_evidence=[direct, transferable, skill, developing, unrelated],
        positioning_themes=[
            PositioningTheme("Managed support escalations", ["e-direct"])
        ],
        development_gaps=["Advanced reporting"],
        structural_gaps=["Production Kubernetes ownership"],
        source_signature="context-signature",
        recommendation="best_match",
        eligible=True,
    )


def _statement(text, claim_type, refs):
    return {"text": text, "claim_type": claim_type, "evidence_refs": refs}


def _valid_output():
    return {
        "candidate_id": "candidate-a",
        "job_id": "job-1",
        "application_context_signature": "context-signature",
        "headline": _statement("Operations specialist", "summary", ["e-direct"]),
        "professional_summary": [
            _statement("Managed support escalations", "summary", ["e-direct"])
        ],
        "key_skills": [_statement("SQL", "skill", ["e-skill"])],
        "experiences": [
            {
                "source_experience_id": "experience-1",
                "company": "Example Ltd",
                "role": "Operations Specialist",
                "bullets": [
                    _statement(
                        "Managed support escalations",
                        "professional_experience",
                        ["e-direct"],
                    )
                ],
            }
        ],
        "additional_relevant_information": [
            _statement(
                "Stakeholder communication",
                "transferable_capability",
                ["e-transferable"],
            ),
            _statement(
                "Developing Kubernetes knowledge",
                "developing_knowledge",
                ["e-developing"],
            ),
        ],
        "schema_version": "tailored-cv-v1",
    }


class FakeGeneratorClient:
    def __init__(self, response=None, error=None):
        self.response = _valid_output() if response is None else response
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response


def _generate(response=None, context=None):
    client = FakeGeneratorClient(response=response)
    result = TailoredCVGenerationService(client).generate(context or _context())
    return result, client


def _codes(result):
    return {issue.code for issue in result.validation_issues}


def test_valid_fake_generation_returns_validated_cv_and_calls_once():
    result, client = _generate()

    assert result.status == "validated"
    assert result.cv.candidate_id == "candidate-a"
    assert len(client.requests) == 1
    assert result.request_signature == client.requests[0].source_signature


def test_json_text_is_parsed_and_provenance_is_preserved():
    result, _ = _generate(json.dumps(_valid_output()))

    assert result.status == "validated"
    bullet = result.cv.experiences[0].bullets[0]
    assert bullet.evidence_refs == ["e-direct"]
    assert result.cv.experiences[0].source_experience_id == "experience-1"


def test_transferable_and_developing_claim_types_are_preserved():
    result, _ = _generate()
    additional = result.cv.additional_relevant_information

    assert [item.claim_type for item in additional] == [
        "transferable_capability",
        "developing_knowledge",
    ]


def test_request_contains_selected_authorized_evidence_only():
    request = build_tailored_cv_generation_request(_context())
    refs = {item["evidence_ref"] for item in request.selected_evidence}

    assert refs == {"e-direct", "e-transferable", "e-skill", "e-developing"}
    assert "e-unrelated" not in refs
    assert "Private unrelated tool" not in request.prompt
    assert "Managed support escalations" in request.prompt


def test_prompt_contains_truth_constraints_and_json_contract():
    prompt = build_tailored_cv_generation_request(_context()).prompt

    assert "You are not creating a candidate" in prompt
    assert "Do not invent responsibilities" in prompt
    assert "Return JSON only" in prompt
    assert "evidence_refs" in prompt
    assert "Production Kubernetes ownership" in prompt


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("candidate_id", "candidate-b", "candidate_mismatch"),
        ("job_id", "job-2", "job_mismatch"),
        (
            "application_context_signature",
            "wrong-signature",
            "context_signature_mismatch",
        ),
    ],
)
def test_wrong_output_identity_is_rejected(field, value, code):
    output = {**_valid_output(), field: value}
    result, _ = _generate(output)

    assert result.status == "validation_failed"
    assert result.cv is None
    assert code in _codes(result)


def test_invented_evidence_ref_fails_truth_guard():
    output = _valid_output()
    output["headline"] = _statement("Invented claim", "summary", ["invented"])
    result, _ = _generate(output)

    assert result.status == "validation_failed"
    assert result.cv is None
    assert "unknown_evidence_ref" in _codes(result)


def test_wrong_source_experience_fails_truth_guard():
    output = _valid_output()
    output["experiences"][0]["source_experience_id"] = "experience-2"
    result, _ = _generate(output)

    assert result.status == "validation_failed"
    assert "experience_source_mismatch" in _codes(result)


def test_missing_provenance_is_a_generation_error():
    output = _valid_output()
    del output["headline"]["evidence_refs"]
    result, _ = _generate(output)

    assert result.status == "generation_error"
    assert result.error_code == "invalid_generator_output"
    assert result.cv is None


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        "[]",
        {"candidate_id": "a"},
        {**_valid_output(), "schema_version": "tailored-cv-v2"},
    ],
)
def test_malformed_output_is_handled_as_generation_error(response):
    result, _ = _generate(response)

    assert result.status == "generation_error"
    assert result.error_code == "invalid_generator_output"
    assert result.cv is None


def test_structural_gap_overclaim_is_not_approved():
    output = _valid_output()
    output["headline"] = _statement(
        "Owned production Kubernetes infrastructure",
        "summary",
        ["e-developing"],
    )
    result, _ = _generate(output)

    assert result.status == "validation_failed"
    assert "protected_gap_conflict" in _codes(result)
    assert result.cv is None


def test_client_exception_is_handled_without_leaking_details():
    client = FakeGeneratorClient(error=RuntimeError("secret provider detail"))
    result = TailoredCVGenerationService(client).generate(_context())

    assert result.status == "generation_error"
    assert result.error_code == "generator_client_error"
    assert "secret provider detail" not in result.error_message
    assert len(client.requests) == 1


@pytest.mark.parametrize(
    "context",
    [
        replace(_context(), eligible=False),
        replace(_context(), recommendation="reject"),
    ],
)
def test_ineligible_context_is_refused_without_calling_client(context):
    client = FakeGeneratorClient()
    result = TailoredCVGenerationService(client).generate(context)

    assert result.error_code == "ineligible_application"
    assert client.requests == []


def test_empty_but_eligible_context_fails_safely_without_client_call():
    context = replace(
        _context(),
        direct_evidence=[],
        transferable_evidence=[],
        supporting_evidence=[],
        developing_evidence=[],
        available_evidence=[],
        positioning_themes=[],
    )
    client = FakeGeneratorClient()
    result = TailoredCVGenerationService(client).generate(context)

    assert result.error_code == "no_selected_evidence"
    assert result.cv is None
    assert client.requests == []


def test_request_and_signature_are_deterministic_and_context_sensitive():
    first = build_tailored_cv_generation_request(_context())
    duplicate = build_tailored_cv_generation_request(_context())
    changed = build_tailored_cv_generation_request(
        replace(_context(), job_title="Changed role")
    )

    assert asdict(first) == asdict(duplicate)
    assert first.source_signature == duplicate.source_signature
    assert first.source_signature != changed.source_signature


def test_request_does_not_contain_available_only_candidate_data():
    serialized = json.dumps(
        asdict(build_tailored_cv_generation_request(_context())),
        sort_keys=True,
    )

    assert "e-unrelated" not in serialized
    assert "Private unrelated tool" not in serialized
