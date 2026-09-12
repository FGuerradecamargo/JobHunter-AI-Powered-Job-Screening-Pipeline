from dataclasses import asdict
import json
from pathlib import Path

import pytest

from models.prepare_application import PrepareApplicationResult
from models.tailored_cv_contract import (
    DraftTailoredCV,
    DraftTailoredCVExperience,
    TailoredCVStatement,
)
from services.prepared_application_ui import (
    build_prepared_cv_view,
    get_prepared_application,
    handle_prepare_application_action,
    is_prepare_application_eligible,
    prepared_application_error_message,
    prepared_application_state_key,
)


def _statement(text, claim_type="summary", refs=None):
    return TailoredCVStatement(
        text=text,
        claim_type=claim_type,
        evidence_refs=list(refs or ["secret-evidence-ref"]),
    )


def _cv(candidate_id="candidate-a", job_id="job-1"):
    return DraftTailoredCV(
        candidate_id=candidate_id,
        job_id=job_id,
        application_context_signature="secret-context-signature",
        headline=_statement("Product Operations Specialist"),
        professional_summary=[_statement("Evidence-led operator")],
        key_skills=[_statement("SQL", "skill")],
        experiences=[
            DraftTailoredCVExperience(
                source_experience_id="secret-experience-id",
                company="Example Ltd",
                role="Operations Specialist",
                bullets=[
                    _statement(
                        "Improved support processes",
                        "professional_experience",
                    )
                ],
            )
        ],
        additional_relevant_information=[
            _statement("Stakeholder communication", "transferable_capability")
        ],
    )


def _prepared(candidate_id="candidate-a", job_id="job-1"):
    return PrepareApplicationResult(
        status="prepared",
        candidate_id=candidate_id,
        job_id=job_id,
        analysis_id="secret-analysis-id",
        application_context_signature="secret-context-signature",
        cv=_cv(candidate_id, job_id),
        generation_status="validated",
    )


class FakePreparationService:
    def __init__(self, result=None):
        self.result = result or _prepared()
        self.calls = []

    def prepare(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.result


@pytest.mark.parametrize(
    "recommendation",
    ["best_match", "potential", "good_opportunity"],
)
def test_eligible_analyzed_opportunity_exposes_prepare_action(recommendation):
    assert is_prepare_application_eligible(
        {"recommendation": recommendation}
    )


@pytest.mark.parametrize("analysis", [{"recommendation": "reject"}, {}, None])
def test_reject_or_ineligible_opportunity_does_not_prepare(analysis):
    service = FakePreparationService()
    result = handle_prepare_application_action(
        {},
        candidate_id="candidate-a",
        job_id="job-1",
        analysis=analysis,
        action_requested=True,
        preparation_service=service,
    )

    assert result.status == "ineligible"
    assert service.calls == []


def test_ordinary_render_does_not_call_preparation_service():
    service = FakePreparationService()
    result = handle_prepare_application_action(
        {},
        candidate_id="candidate-a",
        job_id="job-1",
        analysis={"recommendation": "best_match"},
        action_requested=False,
        preparation_service=service,
    )

    assert result is None
    assert service.calls == []


def test_explicit_action_calls_service_exactly_once_and_stores_result():
    state = {}
    service = FakePreparationService()
    result = handle_prepare_application_action(
        state,
        candidate_id="candidate-a",
        job_id="job-1",
        analysis={"recommendation": "best_match"},
        action_requested=True,
        preparation_service=service,
    )

    assert result.status == "prepared"
    assert service.calls == [("candidate-a", "job-1")]
    assert state[prepared_application_state_key("candidate-a", "job-1")] == result


def test_rerender_reads_cached_result_without_regeneration():
    state = {}
    service = FakePreparationService()
    handle_prepare_application_action(
        state,
        candidate_id="candidate-a",
        job_id="job-1",
        analysis={"recommendation": "best_match"},
        action_requested=True,
        preparation_service=service,
    )
    cached = handle_prepare_application_action(
        state,
        candidate_id="candidate-a",
        job_id="job-1",
        analysis={"recommendation": "best_match"},
        action_requested=False,
        preparation_service=service,
    )

    assert cached == _prepared()
    assert service.calls == [("candidate-a", "job-1")]


def test_candidate_a_result_is_not_visible_to_candidate_b():
    state = {
        prepared_application_state_key("candidate-a", "job-1"): _prepared()
    }

    assert get_prepared_application(
        state,
        candidate_id="candidate-b",
        job_id="job-1",
    ) is None


def test_different_jobs_do_not_share_prepared_state():
    state = {
        prepared_application_state_key("candidate-a", "job-1"): _prepared()
    }

    assert get_prepared_application(
        state,
        candidate_id="candidate-a",
        job_id="job-2",
    ) is None


def test_mismatched_result_is_not_cached_or_rendered():
    state = {}
    service = FakePreparationService(_prepared(candidate_id="candidate-b"))
    result = handle_prepare_application_action(
        state,
        candidate_id="candidate-a",
        job_id="job-1",
        analysis={"recommendation": "best_match"},
        action_requested=True,
        preparation_service=service,
    )

    assert result.error_code == "scope_mismatch"
    assert state == {}


def test_cv_view_model_contains_all_readable_sections():
    view = build_prepared_cv_view(_prepared())

    assert view.headline == "Product Operations Specialist"
    assert view.professional_summary == ["Evidence-led operator"]
    assert view.key_skills == ["SQL"]
    assert view.experiences[0].role == "Operations Specialist"
    assert view.experiences[0].company == "Example Ltd"
    assert view.experiences[0].bullets == ["Improved support processes"]
    assert view.additional_information == ["Stakeholder communication"]
    assert view.status_text == "Validated against your WorkPilot evidence"


def test_normal_view_model_excludes_provenance_and_internal_ids():
    serialized = json.dumps(asdict(build_prepared_cv_view(_prepared())))

    assert "secret-evidence-ref" not in serialized
    assert "secret-experience-id" not in serialized
    assert "secret-context-signature" not in serialized
    assert "secret-analysis-id" not in serialized
    assert "claim_type" not in serialized


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            PrepareApplicationResult(
                status="ineligible",
                candidate_id="candidate-a",
                job_id="job-1",
            ),
            "not eligible",
        ),
        (
            PrepareApplicationResult(
                status="failed",
                candidate_id="candidate-a",
                job_id="job-1",
                error_code="analysis_not_found",
            ),
            "no longer available",
        ),
        (
            PrepareApplicationResult(
                status="generation_failed",
                candidate_id="candidate-a",
                job_id="job-1",
                error_message="private provider detail",
            ),
            "did not pass validation",
        ),
    ],
)
def test_failures_map_to_safe_user_messages(result, expected):
    message = prepared_application_error_message(result)

    assert expected in message
    assert "private provider detail" not in message


def test_preparation_does_not_mutate_application_lifecycle_state():
    state = {
        "opportunity_state:candidate-a:job-1": "in_review",
        "applied_at:candidate-a:job-1": None,
    }
    before = dict(state)
    handle_prepare_application_action(
        state,
        candidate_id="candidate-a",
        job_id="job-1",
        analysis={"recommendation": "best_match"},
        action_requested=True,
        preparation_service=FakePreparationService(),
    )

    assert state["opportunity_state:candidate-a:job-1"] == before[
        "opportunity_state:candidate-a:job-1"
    ]
    assert state["applied_at:candidate-a:job-1"] is None


def test_opportunities_page_wires_only_explicit_button_to_controller():
    source = Path("pages/1_Opportunities.py").read_text(encoding="utf-8")

    assert '"Prepare Application"' in source
    assert "action_requested=prepare_requested" in source
    assert '"_prepare_application_service"' in source
