from dataclasses import asdict
import json
from pathlib import Path

import pytest

from models.interview_context import InterviewContext, InterviewDetails
from models.interview_preparation import InterviewPreparation, PreparationArea
from services.interview_preparation_ui import (
    handle_interview_details_save,
    interview_details_state_key,
    load_interview_preparation_view,
)


def _context(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="secret-analysis-id",
        interview_prep_contract_signature="secret-contract-signature",
        interview_stage="interview",
        job_title="Product Operations Specialist",
        company="Example Ltd",
        interview_type="Technical interview",
        interview_format="Panel",
        interviewer="Alex, Hiring Manager",
        duration_minutes=45,
        scheduled_at="2026-09-20 10:00",
        instructions="Prepare a short case study.",
        source_signature="secret-context-signature",
    )
    values.update(changes)
    return InterviewContext(**values)


def _preparation(**changes):
    areas = [
        PreparationArea(
            topic="SQL",
            source_type="explicit_interview_topic",
            priority="explicit",
            what_they_seek="Explicitly supplied topic.",
            what_to_demonstrate="Describe your real current level.",
            example_direction="Look for a real and verifiable example.",
            emphasis="Be concise.",
            caution="Do not overclaim.",
            evidence_refs=["secret-evidence-ref"],
        ),
        PreparationArea(
            topic="Production Kubernetes",
            source_type="structural_gap",
            priority="high",
            what_they_seek="Capability not supported by evidence.",
            what_to_demonstrate="Explain the boundary honestly.",
            example_direction="Identify genuine adjacent experience.",
            caution="Do not imply production experience.",
            gap_type="structural",
        ),
        PreparationArea(
            topic="Advanced reporting",
            source_type="development_gap",
            priority="normal",
            what_they_seek="Deeper capability.",
            what_to_demonstrate="Describe your current level accurately.",
            example_direction="Use a real learning example.",
            caution="Do not present development as expertise.",
            gap_type="development",
        ),
    ]
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="secret-analysis-id",
        interview_context_signature="secret-context-signature",
        interview_stage="interview",
        summary_guidance="Prepare truthful examples.",
        preparation_areas=areas,
        interview_instructions=["Prepare a short case study."],
        rehearsal_prompts=["Prepare to discuss a real example related to SQL."],
        questions_to_ask_the_company=["What would success look like?"],
        source_signature="secret-preparation-signature",
    )
    values.update(changes)
    return InterviewPreparation(**values)


def _details(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        interview_type="Technical interview",
        interview_format="Panel",
        interviewer="Alex, Hiring Manager",
        duration_minutes=45,
        scheduled_at="2026-09-20 10:00",
        instructions="Prepare a short case study.",
        explicit_topics=["SQL"],
    )
    values.update(changes)
    return InterviewDetails(**values)


class ContextService:
    def __init__(self, value=None, error=None):
        self.value = value or _context()
        self.error = error
        self.calls = []

    def build(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        if self.error:
            raise self.error
        return self.value


class PreparationService:
    def __init__(self, value=None, error=None):
        self.value = value or _preparation()
        self.error = error
        self.calls = []

    def build(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        if self.error:
            raise self.error
        return self.value


class DetailsRepository:
    def __init__(self, value=None, save_error=None):
        self.value = value or _details()
        self.save_error = save_error
        self.reads = []
        self.writes = []

    def get(self, candidate_id, job_id):
        self.reads.append((candidate_id, job_id))
        return self.value

    def save(self, details):
        self.writes.append(details)
        if self.save_error:
            raise self.save_error
        self.value = details
        return details


def _load(*, status="applied", context=None, preparation=None, repository=None):
    return load_interview_preparation_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status=status,
        context_service=context or ContextService(),
        preparation_service=preparation or PreparationService(),
        details_repository=repository or DetailsRepository(),
    )


@pytest.mark.parametrize("stage", ["interview", "final_interview"])
def test_active_interview_stage_shows_interview_prep(stage):
    result = _load(
        context=ContextService(_context(interview_stage=stage)),
        preparation=PreparationService(_preparation(interview_stage=stage)),
    )
    assert result.visible
    assert result.view.stage == ("Interview" if stage == "interview" else "Final interview")


@pytest.mark.parametrize(
    "status", ["rejected_before_interview", "rejected_after_interview", "offer", "user_rejected", "in_review"]
)
def test_ineligible_or_terminal_lifecycle_does_not_show(status):
    context = ContextService()
    preparation = PreparationService()
    repository = DetailsRepository()
    result = _load(status=status, context=context, preparation=preparation, repository=repository)
    assert not result.visible
    assert context.calls == preparation.calls == repository.reads == []


def test_applied_without_interview_is_safely_hidden():
    result = _load(context=ContextService(error=ValueError("not active")))
    assert not result.visible
    assert result.error_message == ""


def test_legacy_in_process_maps_through_existing_context_compatibility():
    assert _load(status="in_process").visible


def test_header_omits_empty_interview_metadata():
    result = _load(context=ContextService(_context(
        interview_type="", interview_format="", interviewer="",
        duration_minutes=None, scheduled_at="",
    )))
    view = result.view
    assert view.interview_type == view.interview_format == view.interviewer == ""
    assert view.duration == view.scheduled_at == ""


def test_view_exposes_no_internal_ids_signatures_or_evidence_refs():
    serialized = json.dumps(asdict(_load().view))
    for secret in (
        "secret-analysis-id", "secret-contract-signature", "secret-context-signature",
        "secret-preparation-signature", "secret-evidence-ref",
    ):
        assert secret not in serialized
    assert "evidence_refs" not in serialized
    assert "schema_version" not in serialized


def test_priority_labels_are_human_readable():
    areas = {area.topic: area for area in _load().view.preparation_areas}
    assert areas["SQL"].priority_label == "Specifically mentioned"
    assert areas["Production Kubernetes"].priority_label == "High priority"
    assert areas["Advanced reporting"].priority_label == "Prepare"


def test_explicit_and_gap_labels_are_careful_not_predictive_or_shaming():
    areas = {area.topic: area for area in _load().view.preparation_areas}
    assert areas["SQL"].source_label == "Specifically mentioned for this interview"
    assert areas["Production Kubernetes"].source_label == "Be precise here"
    assert areas["Advanced reporting"].source_label == "This is still developing"
    assert "will definitely" not in str(asdict(_load().view)).casefold()


def test_instructions_rehearsals_and_company_questions_are_presented():
    view = _load().view
    assert view.interview_instructions == ["Prepare a short case study."]
    assert view.rehearsal_prompts[0].startswith("Prepare to discuss")
    assert "interviewer will ask" not in view.rehearsal_prompts[0].casefold()
    assert view.questions_to_ask_the_company == ["What would success look like?"]


def test_normal_render_performs_reads_but_zero_writes():
    repository = DetailsRepository()
    result = _load(repository=repository)
    assert result.visible
    assert repository.reads == [("candidate-a", "job-1")]
    assert repository.writes == []


def test_changing_inputs_without_save_performs_zero_writes():
    repository = DetailsRepository()
    result = handle_interview_details_save(
        {}, candidate_id="candidate-a", job_id="job-1", lifecycle_status="applied",
        save_requested=False, details=_details(interview_type="Case study"),
        details_repository=repository, context_service=ContextService(),
        preparation_service=PreparationService(),
    )
    assert result.visible
    assert repository.writes == []


def test_explicit_save_writes_once_and_rebuilds_preparation():
    state = {}
    repository = DetailsRepository()
    context = ContextService()
    preparation = PreparationService()
    updated = _details(interview_type="Case study")
    result = handle_interview_details_save(
        state, candidate_id="candidate-a", job_id="job-1", lifecycle_status="applied",
        save_requested=True, details=updated, details_repository=repository,
        context_service=context, preparation_service=preparation,
    )
    assert result.saved
    assert repository.writes == [updated]
    assert context.calls == [("candidate-a", "job-1")]
    assert preparation.calls == [("candidate-a", "job-1")]
    assert state[interview_details_state_key("candidate-a", "job-1")] == updated


def test_save_does_not_mutate_lifecycle_or_outcome_state():
    state = {"lifecycle:candidate-a:job-1": "interview", "outcome:candidate-a:job-1": ""}
    before = dict(state)
    handle_interview_details_save(
        state, candidate_id="candidate-a", job_id="job-1", lifecycle_status="applied",
        save_requested=True, details=_details(interview_type="Final interview"),
        details_repository=DetailsRepository(), context_service=ContextService(),
        preparation_service=PreparationService(),
    )
    assert state["lifecycle:candidate-a:job-1"] == before["lifecycle:candidate-a:job-1"]
    assert state["outcome:candidate-a:job-1"] == before["outcome:candidate-a:job-1"]


def test_session_state_key_is_scoped_by_candidate_and_job():
    keys = {
        interview_details_state_key("candidate-a", "job-1"),
        interview_details_state_key("candidate-b", "job-1"),
        interview_details_state_key("candidate-a", "job-2"),
    }
    assert len(keys) == 3


@pytest.mark.parametrize(
    "context,preparation,details",
    [
        (_context(candidate_id="candidate-b"), _preparation(), _details()),
        (_context(job_id="job-2"), _preparation(), _details()),
        (_context(), _preparation(candidate_id="candidate-b"), _details()),
        (_context(), _preparation(), _details(job_id="job-2")),
    ],
)
def test_scope_mismatch_fails_safely(context, preparation, details):
    result = _load(
        context=ContextService(context),
        preparation=PreparationService(preparation),
        repository=DetailsRepository(details),
    )
    assert not result.visible
    assert result.error_message
    assert "candidate-a" not in result.error_message
    assert "job-1" not in result.error_message


def test_failed_save_does_not_claim_success_or_replace_session_state():
    state = {interview_details_state_key("candidate-a", "job-1"): _details()}
    before = dict(state)
    result = handle_interview_details_save(
        state, candidate_id="candidate-a", job_id="job-1", lifecycle_status="applied",
        save_requested=True, details=_details(interview_type="Case study"),
        details_repository=DetailsRepository(save_error=RuntimeError("secret database id")),
        context_service=ContextService(), preparation_service=PreparationService(),
    )
    assert not result.saved
    assert state == before
    assert "secret" not in result.error_message


def test_prepared_cv_is_not_required_by_ui_boundary():
    source = Path("services/interview_preparation_ui.py").read_text(encoding="utf-8")
    assert "prepared_cv" not in source
    assert _load().visible


def test_dashboard_uses_deterministic_ui_boundary_and_explicit_save():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "load_interview_preparation_view(" in source
    assert "handle_interview_details_save(" in source
    assert '"Save interview details"' in source
    assert "analysis.get(\n                \"interview_prep\"" not in source
    assert "mark_final_interview" not in source[source.index("def render_interview_preparation"):source.index("def render_job")]


def test_ui_has_no_ai_api_or_generator_path():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in ("services/interview_preparation_ui.py", "app.py")
    ).lower()
    assert "openai" not in source
    assert "llm" not in source
    assert "prepare interview ai" not in source
    assert ".generate(" not in source
    assert "requests." not in source
