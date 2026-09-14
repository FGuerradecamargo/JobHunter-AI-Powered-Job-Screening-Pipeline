from contextlib import contextmanager
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3

import pytest

from models.application_contract import ApplicationEvidenceRef
from models.interview_context import InterviewContext, InterviewDetails
from models.interview_feedback import InterviewFeedback
from models.interview_preparation import InterviewPreparation
from services.database import create_interview_feedback_schema
from services.interview_feedback_repository import InterviewFeedbackRepository
from services.interview_feedback_service import InterviewFeedbackService
from services.interview_preparation_builder import build_interview_preparation
from services.interview_preparation_service import InterviewPreparationService
from services.interview_preparation_ui import (
    handle_interview_feedback_save,
    interview_feedback_state_key,
    load_interview_preparation_view,
)
import services.interview_feedback_repository as repository_module


def _evidence():
    return ApplicationEvidenceRef(
        evidence_ref="e-sql",
        source_type="professional_experience",
        source_id="experience-1",
        authority="professional_fact",
        statement="SQL",
    )


def _context(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        interview_prep_contract_signature="contract-signature",
        interview_stage="interview",
        job_title="Operations Lead",
        company="Example Ltd",
        authorized_evidence=[_evidence()],
        source_signature="context-signature",
    )
    values.update(changes)
    return InterviewContext(**values)


def _feedback(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        interview_stage="interview",
        recruiter_feedback="Bring stronger examples of strategic ownership.",
        candidate_notes="I felt shaky on SQL.",
        discussed_topics=["SQL", "Stakeholder management"],
        difficult_topics=["Commercial strategy"],
        next_stage_instructions="Prepare a stakeholder case study.",
    )
    values.update(changes)
    return InterviewFeedback(**values)


@pytest.fixture
def feedback_repository(tmp_path, monkeypatch):
    path = tmp_path / "feedback.db"

    @contextmanager
    def connect():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    with connect() as connection:
        connection.execute("CREATE TABLE candidates (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE candidate_job_analyses (candidate_id TEXT, job_id TEXT, PRIMARY KEY(candidate_id, job_id))"
        )
        connection.executemany("INSERT INTO candidates VALUES (?)", [("candidate-a",), ("candidate-b",)])
        connection.executemany("INSERT INTO jobs VALUES (?)", [("job-1",), ("job-2",)])
        connection.execute("INSERT INTO candidate_job_analyses VALUES (?, ?)", ("candidate-a", "job-1"))
        create_interview_feedback_schema(connection)
    monkeypatch.setattr(repository_module, "get_connection", connect)
    return InterviewFeedbackRepository()


def test_feedback_persists_in_dedicated_structure(feedback_repository):
    saved = feedback_repository.save(_feedback())
    assert saved.recruiter_feedback.startswith("Bring stronger")
    assert saved.candidate_notes == "I felt shaky on SQL."
    assert saved.discussed_topics == ["SQL", "Stakeholder management"]
    assert saved.created_at and saved.updated_at


def test_feedback_updates_single_checkpoint_without_event_history(feedback_repository):
    first = feedback_repository.save(_feedback())
    second = feedback_repository.save(_feedback(candidate_notes="Updated notes"))
    assert second.created_at == first.created_at
    assert second.candidate_notes == "Updated notes"
    source = Path("services/database.py").read_text(encoding="utf-8")
    assert "candidate_interview_feedback_events" not in source


def test_feedback_repository_requires_candidate_job_relationship(feedback_repository):
    with pytest.raises(ValueError, match="relationship"):
        feedback_repository.save(_feedback(candidate_id="candidate-b"))


def test_feedback_sources_remain_distinct_in_preparation():
    result = build_interview_preparation(_context(), feedback=_feedback())
    assert [(item.source_type, item.text) for item in result.explicit_feedback] == [
        ("recruiter_feedback", "Bring stronger examples of strategic ownership."),
        ("candidate_self_report", "I felt shaky on SQL."),
    ]
    assert all(item.evidence_refs == [] for item in result.explicit_feedback)


def test_topics_and_instructions_are_structured_without_becoming_evidence():
    result = build_interview_preparation(_context(), feedback=_feedback())
    assert result.previously_discussed_topics == ["SQL", "Stakeholder management"]
    assert result.review_topics == ["Commercial strategy"]
    assert result.next_stage_instructions == ["Prepare a stakeholder case study."]
    assert result.preparation_areas == []
    assert all(
        item.evidence_refs == []
        for item in result.explicit_feedback
    )


def test_feedback_guidance_contains_no_causal_or_unsupported_claims():
    output = json.dumps(asdict(build_interview_preparation(_context(), feedback=_feedback()))).casefold()
    assert "because you lack" not in output
    assert "interviewer rejected you because" not in output
    assert "you are weak" not in output
    assert "you have strategic ownership" not in output
    assert "verified professional fact" in output


def test_final_interview_can_use_feedback_captured_at_prior_interview():
    result = build_interview_preparation(
        _context(interview_stage="final_interview"),
        feedback=_feedback(interview_stage="interview"),
    )
    assert result.interview_stage == "final_interview"
    assert result.explicit_feedback
    assert "decision-level" in result.summary_guidance


@pytest.mark.parametrize(
    "feedback,error",
    [
        (_feedback(candidate_id="candidate-b"), "another candidate"),
        (_feedback(job_id="job-2"), "another job"),
        (_feedback(interview_stage="offer"), "stage scope"),
    ],
)
def test_feedback_scope_mismatch_fails_closed(feedback, error):
    with pytest.raises(PermissionError, match=error):
        build_interview_preparation(_context(), feedback=feedback)


def test_material_feedback_changes_preparation_signature():
    base = build_interview_preparation(_context(), feedback=_feedback())
    changed = build_interview_preparation(
        _context(), feedback=_feedback(difficult_topics=["Architecture"])
    )
    assert base.source_signature != changed.source_signature


def test_feedback_signature_ignores_whitespace_case_and_topic_order():
    first = build_interview_preparation(_context(), feedback=_feedback())
    noisy = _feedback(
        recruiter_feedback="  BRING stronger examples of strategic ownership. ",
        candidate_notes=" i FELT shaky on sql. ",
        discussed_topics=[" stakeholder   MANAGEMENT ", " sql "],
        difficult_topics=[" commercial   STRATEGY "],
        next_stage_instructions=" prepare a stakeholder CASE study. ",
    )
    second = build_interview_preparation(_context(), feedback=noisy)
    assert first.source_signature == second.source_signature


class ContextService:
    def __init__(self, context=None):
        self.context = context or _context()
        self.calls = []

    def build(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.context


class FeedbackRepository:
    def __init__(self, feedback=None):
        self.feedback = feedback
        self.reads = []
        self.writes = []

    def get(self, candidate_id, job_id):
        self.reads.append((candidate_id, job_id))
        return self.feedback

    def save(self, feedback):
        self.writes.append(feedback)
        self.feedback = feedback
        return feedback


def test_preparation_service_reads_feedback_and_preserves_scope():
    repository = FeedbackRepository(_feedback())
    result = InterviewPreparationService(
        context_service=ContextService(), feedback_repository=repository
    ).build("candidate-a", "job-1")
    assert result.explicit_feedback
    assert repository.reads == [("candidate-a", "job-1")]


def test_feedback_service_takes_stage_from_authoritative_context():
    repository = FeedbackRepository()
    service = InterviewFeedbackService(
        context_service=ContextService(_context(interview_stage="final_interview")),
        repository=repository,
    )
    saved = service.save(
        "candidate-a", "job-1", candidate_notes="This was a final interview"
    )
    assert saved.interview_stage == "final_interview"
    assert repository.writes == [saved]


class PreparationService:
    def __init__(self, feedback=None):
        self.feedback = feedback
        self.calls = []

    def build(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return build_interview_preparation(_context(), feedback=self.feedback)


class DetailsRepository:
    def get(self, candidate_id, job_id):
        return InterviewDetails(candidate_id=candidate_id, job_id=job_id)


class FeedbackSaveService:
    def __init__(self, repository):
        self.repository = repository
        self.calls = []

    def save(self, candidate_id, job_id, **values):
        self.calls.append((candidate_id, job_id, values))
        return self.repository.save(
            InterviewFeedback(
                candidate_id=candidate_id,
                job_id=job_id,
                interview_stage="interview",
                **values,
            )
        )


def _ui_save(save_requested, repository=None):
    repository = repository or FeedbackRepository(_feedback())
    save_service = FeedbackSaveService(repository)
    preparation = PreparationService(repository.feedback)
    result = handle_interview_feedback_save(
        {}, candidate_id="candidate-a", job_id="job-1", lifecycle_status="applied",
        save_requested=save_requested, recruiter_feedback="Explicit feedback",
        candidate_notes="Self-report", discussed_topics=["SQL"],
        difficult_topics=["Strategy"], next_stage_instructions="Prepare a case",
        feedback_service=save_service, feedback_repository=repository,
        context_service=ContextService(), preparation_service=preparation,
        details_repository=DetailsRepository(),
    )
    return result, repository, save_service, preparation


def test_render_or_edit_without_save_performs_zero_feedback_writes():
    result, repository, save_service, _ = _ui_save(False)
    assert result.visible
    assert repository.writes == []
    assert save_service.calls == []


def test_explicit_feedback_save_writes_once_and_rebuilds():
    result, repository, save_service, preparation = _ui_save(True)
    assert result.saved
    assert len(repository.writes) == 1
    assert len(save_service.calls) == 1
    assert preparation.calls == [("candidate-a", "job-1")]


def test_feedback_save_does_not_touch_lifecycle_outcome_or_career_evidence():
    state = {
        "lifecycle:candidate-a:job-1": "interview",
        "outcome:candidate-a:job-1": "",
        "career_evidence:candidate-a": ["existing"],
    }
    repository = FeedbackRepository(_feedback())
    service = FeedbackSaveService(repository)
    handle_interview_feedback_save(
        state, candidate_id="candidate-a", job_id="job-1", lifecycle_status="applied",
        save_requested=True, recruiter_feedback="Feedback", candidate_notes="Notes",
        discussed_topics=[], difficult_topics=[], next_stage_instructions="",
        feedback_service=service, feedback_repository=repository,
        context_service=ContextService(), preparation_service=PreparationService(),
        details_repository=DetailsRepository(),
    )
    assert state["lifecycle:candidate-a:job-1"] == "interview"
    assert state["outcome:candidate-a:job-1"] == ""
    assert state["career_evidence:candidate-a"] == ["existing"]


def test_feedback_session_key_is_candidate_and_job_scoped():
    assert len({
        interview_feedback_state_key("candidate-a", "job-1"),
        interview_feedback_state_key("candidate-b", "job-1"),
        interview_feedback_state_key("candidate-a", "job-2"),
    }) == 3


def test_terminal_state_never_reads_or_exposes_active_feedback_controls():
    repository = FeedbackRepository(_feedback())
    result = load_interview_preparation_view(
        candidate_id="candidate-a", job_id="job-1", lifecycle_status="offer",
        context_service=ContextService(), preparation_service=PreparationService(),
        details_repository=DetailsRepository(), feedback_repository=repository,
    )
    assert not result.visible
    assert repository.reads == []


def test_feedback_has_no_career_evidence_ai_api_or_network_path():
    paths = (
        "models/interview_feedback.py",
        "services/interview_feedback_repository.py",
        "services/interview_feedback_service.py",
        "services/interview_preparation_builder.py",
        "services/interview_preparation_ui.py",
    )
    source = "\n".join(Path(path).read_text(encoding="utf-8") for path in paths).lower()
    assert "career_evidence" not in source
    assert "openai" not in source
    assert "llm" not in source
    assert "requests." not in source
    assert ".generate(" not in source


def test_dashboard_uses_explicit_feedback_save_without_outcome_transition():
    source = Path("app.py").read_text(encoding="utf-8")
    section = source[source.index("def render_interview_preparation"):source.index("def render_job")]
    assert '"Save interview feedback"' in section
    assert "handle_interview_feedback_save(" in section
    assert "mark_interview" not in section
    assert "mark_final_interview" not in section
    assert "mark_offer" not in section
