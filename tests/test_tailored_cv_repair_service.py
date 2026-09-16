from dataclasses import asdict, replace
import json

import pytest

from models.prepare_application import PrepareApplicationResult
from services.prepared_application_ui import prepared_application_error_message

from models.application_context import ApplicationContext
from models.application_contract import ApplicationEvidenceRef
from models.tailored_cv_contract import CVValidationIssue, TailoredCVRepairRequest
from services.tailored_cv_generation_request_builder import (
    build_tailored_cv_generation_request,
)
from services.tailored_cv_generation_service import TailoredCVGenerationService
from services.tailored_cv_parser import parse_tailored_cv_response
from services.tailored_cv_repair_request_builder import (
    build_tailored_cv_repair_request,
)


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
    developing = _evidence(
        "e-developing",
        "developing_capability",
        "candidate:developing",
        "developing_evidence",
        "Kubernetes fundamentals",
    )
    unrelated = _evidence(
        "e-unrelated",
        "skill",
        "candidate:skills",
        "candidate_profile_fact",
        "Private unrelated tool",
    )
    return ApplicationContext(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        contract_signature="contract-signature",
        direct_evidence=[direct],
        transferable_evidence=[transferable],
        developing_evidence=[developing],
        available_evidence=[direct, transferable, developing, unrelated],
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
        "key_skills": [],
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


def _invalid_unknown():
    output = _valid_output()
    output["headline"] = _statement("Invented claim", "summary", ["invented"])
    return output


class SequenceGeneratorClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        response = self.responses[len(self.requests) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _run(*responses, max_repair_attempts=1, context=None):
    client = SequenceGeneratorClient(*responses)
    service = TailoredCVGenerationService(
        client,
        max_repair_attempts=max_repair_attempts,
    )
    return service.generate(context or _context()), client


def _codes(result):
    return {item.code for item in result.validation_issues}


@pytest.mark.parametrize("ending,stage,repair", [
    ("disabled", "initial_truth_guard", False),
    ("success", "validated_after_repair", True),
    ("invalid", "repair_truth_guard", True),
    ("parse", "repair_parse", True),
    ("client", "repair_client", True),
])
def test_content_free_validation_diagnostics(caplog, ending, stage, repair):
    private = "PRIVATE-CV-SECRET-SENTINEL"
    invalid = _invalid_unknown()
    invalid["headline"]["text"] = private
    invalid["headline"]["evidence_refs"] = [private]
    responses = [invalid]
    if repair:
        responses.append({
            "success": _valid_output(), "invalid": invalid,
            "parse": private, "client": RuntimeError(private),
        }[ending])
    result, client = _run(*responses, max_repair_attempts=int(repair))
    events = [json.loads(record.message) for record in caplog.records
              if record.name == "services.tailored_cv_diagnostics"]
    assert events[-1]["stage"] == stage
    assert events[-1]["repair_attempted"] is repair
    assert events[0]["validation_codes"] == ["unknown_evidence_ref"]
    assert events[0]["issue_count"] == 1
    assert len(client.requests) == 1 + int(repair)
    assert private not in caplog.text
    assert "candidate-a" not in caplog.text
    if ending == "success":
        assert result.status == "validated_after_repair"
    else:
        message = prepared_application_error_message(PrepareApplicationResult(
            status="generation_failed", candidate_id="candidate-a", job_id="job-1",
            error_code=result.error_code, validation_issues=result.validation_issues,
        ))
        assert private not in message
        if ending == "invalid":
            assert "Repair attempt also failed validation" in message
            assert "Unsupported evidence reference" in message


def test_initial_parse_failure_diagnostic(caplog):
    result, client = _run("PRIVATE INVALID JSON")
    event = json.loads(caplog.records[-1].message)
    assert event["stage"] == "initial_parse"
    assert event["repair_attempted"] is False
    assert event["issue_count"] == 0
    assert len(client.requests) == 1
    assert "PRIVATE INVALID JSON" not in caplog.text
    assert result.error_code == "invalid_generator_output"


def test_untrusted_issue_details_are_not_displayed_or_logged(caplog):
    from services.tailored_cv_diagnostics import log_cv_diagnostic
    issue = CVValidationIssue(code="PRIVATE", location="PRIVATE", message="PRIVATE")
    log_cv_diagnostic(stage="PRIVATE", issues=[issue], error_code="PRIVATE")
    message = prepared_application_error_message(PrepareApplicationResult(
        status="generation_failed", candidate_id="a", job_id="b",
        error_message="PRIVATE", validation_issues=[issue],
    ))
    assert "PRIVATE" not in message + caplog.text


@pytest.mark.parametrize("code,expected", [
    ("generation_in_progress", "already being generated"),
    ("generation_claim_failed", "temporarily unavailable"),
    ("generator_client_error", "generation could not be completed"),
    ("invalid_generator_output", "structure was invalid"),
])
def test_generation_errors_are_not_all_reported_as_truth_guard_failure(code, expected):
    result = PrepareApplicationResult(status="generation_failed", candidate_id="a", job_id="b", error_code=code)
    assert expected in prepared_application_error_message(result)


def test_initial_valid_generation_does_not_repair():
    result, client = _run(_valid_output())

    assert result.status == "validated"
    assert result.attempt_count == 1
    assert result.repair_signature == ""
    assert len(client.requests) == 1


def test_invalid_draft_then_valid_repair_is_approved_after_truth_guard():
    result, client = _run(_invalid_unknown(), _valid_output())

    assert result.status == "validated_after_repair"
    assert result.cv.candidate_id == "candidate-a"
    assert result.attempt_count == 2
    assert result.repair_signature
    assert len(client.requests) == 2
    assert isinstance(client.requests[1], TailoredCVRepairRequest)


def test_repair_request_contains_issues_previous_draft_and_valid_statements():
    _, client = _run(_invalid_unknown(), _valid_output())
    repair = client.requests[1]

    assert repair.validation_issues[0]["code"] == "unknown_evidence_ref"
    assert repair.validation_issues[0]["location"] == "headline"
    assert repair.previous_draft["professional_summary"][0]["text"] == (
        "Managed support escalations"
    )
    assert "previous tailored CV output failed validation" in repair.prompt
    assert "Return JSON only" in repair.prompt


def test_repair_request_contains_only_original_selected_evidence():
    _, client = _run(_invalid_unknown(), _valid_output())
    repair = client.requests[1]
    refs = {item["evidence_ref"] for item in repair.selected_evidence}

    assert refs == {"e-direct", "e-transferable", "e-developing"}
    assert "e-unrelated" not in refs
    assert "Private unrelated tool" not in repair.prompt


def test_repair_cannot_introduce_unknown_evidence():
    result, client = _run(_invalid_unknown(), _invalid_unknown())

    assert result.status == "validation_failed"
    assert result.error_code == "repair_exhausted"
    assert result.cv is None
    assert "unknown_evidence_ref" in _codes(result)
    assert len(client.requests) == 2


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
def test_repair_cannot_change_identity(field, value, code):
    repaired = {**_valid_output(), field: value}
    result, client = _run(
        _invalid_unknown(),
        repaired,
    )

    assert result.status == "validation_failed"
    assert result.cv is None
    assert code in _codes(result)
    assert len(client.requests) == 2


@pytest.mark.parametrize(
    ("claim_type", "reference", "code"),
    [
        (
            "professional_experience",
            "e-developing",
            "developing_evidence_overclaim",
        ),
        (
            "professional_experience",
            "e-transferable",
            "transferable_evidence_overclaim",
        ),
    ],
)
def test_repair_cannot_promote_lower_authority_evidence(
    claim_type,
    reference,
    code,
):
    repaired = _valid_output()
    repaired["headline"] = _statement("Direct expert", claim_type, [reference])
    result, _ = _run(_invalid_unknown(), repaired)

    assert result.status == "validation_failed"
    assert code in _codes(result)
    assert result.cv is None


def test_wrong_source_experience_still_fails_after_repair():
    repaired = _valid_output()
    repaired["experiences"][0]["source_experience_id"] = "experience-2"
    result, _ = _run(_invalid_unknown(), repaired)

    assert result.status == "validation_failed"
    assert "experience_source_mismatch" in _codes(result)


def test_protected_structural_gap_is_still_enforced_after_repair():
    repaired = _valid_output()
    repaired["headline"] = _statement(
        "Owned production Kubernetes infrastructure",
        "summary",
        ["e-developing"],
    )
    result, _ = _run(_invalid_unknown(), repaired)

    assert result.status == "validation_failed"
    assert "protected_gap_conflict" in _codes(result)


def test_default_maximum_is_one_repair_attempt():
    result, client = _run(_invalid_unknown(), _invalid_unknown())

    assert result.attempt_count == 2
    assert len(client.requests) == 2


def test_more_than_one_repair_attempt_is_rejected():
    with pytest.raises(ValueError, match="zero or one"):
        _run(_invalid_unknown(), max_repair_attempts=2)


def test_zero_repairs_preserves_initial_validation_failure():
    result, client = _run(_invalid_unknown(), max_repair_attempts=0)

    assert result.status == "validation_failed"
    assert result.error_code == "truth_guard_rejected"
    assert result.attempt_count == 1
    assert len(client.requests) == 1


def test_generator_exception_during_repair_fails_safely():
    result, client = _run(
        _invalid_unknown(),
        RuntimeError(" fly-by-night provider detail "),
    )

    assert result.status == "repair_failed"
    assert result.error_code == "repair_client_error"
    assert "provider detail" not in result.error_message
    assert result.cv is None
    assert len(client.requests) == 2


def test_malformed_repair_output_fails_without_another_attempt():
    result, client = _run(_invalid_unknown(), "not-json")

    assert result.status == "repair_failed"
    assert result.error_code == "invalid_repair_output"
    assert result.cv is None
    assert len(client.requests) == 2


def test_identity_failure_on_initial_draft_is_not_repaired():
    output = {**_valid_output(), "candidate_id": "candidate-b"}
    result, client = _run(output, _valid_output())

    assert result.status == "validation_failed"
    assert result.attempt_count == 1
    assert len(client.requests) == 1


@pytest.mark.parametrize(
    "context,error_code",
    [
        (replace(_context(), eligible=False), "ineligible_application"),
        (
            replace(
                _context(),
                direct_evidence=[],
                transferable_evidence=[],
                developing_evidence=[],
            ),
            "no_selected_evidence",
        ),
    ],
)
def test_pre_generation_refusals_never_call_client(context, error_code):
    client = SequenceGeneratorClient()
    result = TailoredCVGenerationService(client).generate(context)

    assert result.error_code == error_code
    assert result.attempt_count == 0
    assert client.requests == []


def test_repair_request_signature_is_deterministic_and_input_sensitive():
    original = build_tailored_cv_generation_request(_context())
    draft = parse_tailored_cv_response(_invalid_unknown())
    issue = CVValidationIssue("unknown_evidence_ref", "headline", "Unknown.")
    first = build_tailored_cv_repair_request(
        original_request=original,
        previous_draft=draft,
        validation_issues=[issue],
    )
    duplicate = build_tailored_cv_repair_request(
        original_request=original,
        previous_draft=draft,
        validation_issues=[issue],
    )
    changed_issue = build_tailored_cv_repair_request(
        original_request=original,
        previous_draft=draft,
        validation_issues=[replace(issue, location="professional_summary[0]")],
    )
    changed_draft = build_tailored_cv_repair_request(
        original_request=original,
        previous_draft=replace(draft, job_id="job-2"),
        validation_issues=[issue],
    )
    changed_original = build_tailored_cv_repair_request(
        original_request=replace(original, source_signature="changed"),
        previous_draft=draft,
        validation_issues=[issue],
    )

    assert asdict(first) == asdict(duplicate)
    assert first.source_signature != changed_issue.source_signature
    assert first.source_signature != changed_draft.source_signature
    assert first.source_signature != changed_original.source_signature


def test_negative_repair_limit_is_rejected_before_client_use():
    client = SequenceGeneratorClient()

    with pytest.raises(ValueError, match="zero or one"):
        TailoredCVGenerationService(client, max_repair_attempts=-1)

    assert client.requests == []
