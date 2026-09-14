from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest

from models.interview_context import InterviewContext, InterviewDetails
from models.interview_feedback import InterviewFeedback
from models.interview_prep_contract import InterviewPrepContract
from models.interview_preparation import InterviewPreparation
from services import database
from services.database import (
    create_interview_details_schema,
    create_interview_feedback_schema,
)
from services.interview_context_builder import build_interview_context
from services.interview_details_repository import (
    InterviewDetailsDataError,
    InterviewDetailsRepository,
)
from services.interview_feedback_repository import (
    InterviewFeedbackDataError,
    InterviewFeedbackRepository,
)
from services.interview_feedback_service import InterviewFeedbackService
from services.interview_preparation_builder import build_interview_preparation
from services.interview_preparation_ui import load_interview_preparation_view
import services.interview_details_repository as details_repository_module
import services.interview_feedback_repository as feedback_repository_module


ROOT = Path(__file__).resolve().parents[1]


def _contract(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        application_context_signature="application-context-signature",
        interview_stage="interview",
        application_final_status="",
        eligible=True,
        source_signature="interview-contract-signature",
    )
    values.update(changes)
    return InterviewPrepContract(**values)


def _context(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        interview_prep_contract_signature="interview-contract-signature",
        interview_stage="interview",
        source_signature="interview-context-signature",
    )
    values.update(changes)
    return InterviewContext(**values)


def _feedback(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        interview_stage="interview",
    )
    values.update(changes)
    return InterviewFeedback(**values)


class _RecordingConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, *_args):
        self.statements.append(" ".join(statement.split()))
        return self


@pytest.mark.parametrize(
    "creator,table",
    [
        (create_interview_details_schema, "candidate_interview_details"),
        (create_interview_feedback_schema, "candidate_interview_feedback"),
    ],
)
def test_postgres_interview_tables_enable_server_only_rls(monkeypatch, creator, table):
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    connection = _RecordingConnection()
    creator(connection)
    sql = "\n".join(connection.statements).casefold()
    assert f"alter table {table} enable row level security" in sql
    assert "create policy" not in sql
    assert " grant " not in f" {sql} "
    assert " anon " not in f" {sql} "
    assert " authenticated " not in f" {sql} "


def test_sqlite_interview_schema_does_not_execute_rls(monkeypatch):
    monkeypatch.setattr(database, "is_postgres", lambda: False)
    connection = _RecordingConnection()
    create_interview_details_schema(connection)
    create_interview_feedback_schema(connection)
    assert "ROW LEVEL SECURITY" not in "\n".join(connection.statements)


def test_rls_helper_rejects_unapproved_dynamic_table(monkeypatch):
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    with pytest.raises(ValueError, match="not approved"):
        database._enable_server_only_row_level_security(
            _RecordingConnection(), "candidate_job_analyses"
        )


@pytest.fixture
def interview_database(tmp_path, monkeypatch):
    path = tmp_path / "sprint-12-hardening.db"

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
            "CREATE TABLE candidate_job_analyses ("
            "candidate_id TEXT, job_id TEXT, PRIMARY KEY(candidate_id, job_id))"
        )
        connection.execute("INSERT INTO candidates VALUES ('candidate-a')")
        connection.execute("INSERT INTO jobs VALUES ('job-1')")
        connection.execute(
            "INSERT INTO candidate_job_analyses VALUES ('candidate-a', 'job-1')"
        )
        create_interview_details_schema(connection)
        create_interview_feedback_schema(connection)
    monkeypatch.setattr(details_repository_module, "get_connection", connect)
    monkeypatch.setattr(feedback_repository_module, "get_connection", connect)
    return connect


@pytest.mark.parametrize("payload", ["not-json", "{}", '["SQL", 7]'])
def test_malformed_persisted_detail_topics_fail_safely(interview_database, payload):
    with interview_database() as connection:
        connection.execute(
            "INSERT INTO candidate_interview_details ("
            "candidate_id, job_id, explicit_topics_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("candidate-a", "job-1", payload, "created", "updated"),
        )
    with pytest.raises(InterviewDetailsDataError, match="topic"):
        InterviewDetailsRepository().get("candidate-a", "job-1")


@pytest.mark.parametrize("column", ["discussed_topics_json", "difficult_topics_json"])
def test_malformed_persisted_feedback_topics_fail_safely(interview_database, column):
    with interview_database() as connection:
        connection.execute(
            "INSERT INTO candidate_interview_feedback ("
            "candidate_id, job_id, interview_stage, created_at, updated_at) "
            "VALUES ('candidate-a', 'job-1', 'interview', 'created', 'updated')"
        )
        connection.execute(
            f"UPDATE candidate_interview_feedback SET {column} = ?",
            (json.dumps({"SQL": True}),),
        )
    with pytest.raises(InterviewFeedbackDataError, match="topic"):
        InterviewFeedbackRepository().get("candidate-a", "job-1")


def test_repository_rejects_non_text_topics_before_write(interview_database):
    with pytest.raises(InterviewDetailsDataError, match="only text"):
        InterviewDetailsRepository().save(
            InterviewDetails(
                candidate_id="candidate-a", job_id="job-1", explicit_topics=[7]
            )
        )
    with pytest.raises(InterviewFeedbackDataError, match="only text"):
        InterviewFeedbackRepository().save(
            _feedback(discussed_topics=[{"topic": "SQL"}])
        )


@pytest.mark.parametrize(
    "missing",
    ["analysis_id", "application_context_signature", "source_signature"],
)
def test_context_builder_rejects_incomplete_contract_signatures(missing):
    with pytest.raises(ValueError, match="signatures"):
        build_interview_context(contract=replace(_contract(), **{missing: ""}))


def test_preparation_rejects_missing_upstream_contract_signature():
    with pytest.raises(ValueError, match="incomplete"):
        build_interview_preparation(
            replace(_context(), interview_prep_contract_signature="")
        )


def test_equivalent_iterative_topics_are_deduplicated():
    result = build_interview_preparation(
        _context(explicit_topics=["SQL", " sql ", "Sql"]),
        feedback=_feedback(
            discussed_topics=["Stakeholder Management", " stakeholder  management "],
            difficult_topics=["Commercial Strategy", "commercial strategy"],
        ),
    )
    assert [area.topic for area in result.preparation_areas] == ["SQL"]
    assert result.previously_discussed_topics == ["Stakeholder Management"]
    assert result.review_topics == ["Commercial Strategy"]


class _ContextService:
    def __init__(self, value):
        self.value = value

    def build(self, *_args):
        return self.value


class _Repository:
    def __init__(self, value=None):
        self.value = value

    def get(self, *_args):
        return self.value

    def save(self, _value):
        return self.value


def test_feedback_service_rejects_forged_repository_return_scope():
    service = InterviewFeedbackService(
        context_service=_ContextService(_context()),
        repository=_Repository(_feedback(candidate_id="candidate-b")),
    )
    with pytest.raises(PermissionError, match="another scope"):
        service.save("candidate-a", "job-1")


def test_feedback_service_rejects_stale_repository_return_stage():
    service = InterviewFeedbackService(
        context_service=_ContextService(_context(interview_stage="final_interview")),
        repository=_Repository(_feedback(interview_stage="interview")),
    )
    with pytest.raises(PermissionError, match="stale stage"):
        service.save("candidate-a", "job-1")


def test_ui_fails_closed_on_context_signature_mismatch():
    preparation = build_interview_preparation(_context())
    forged = replace(preparation, interview_context_signature="other-signature")
    result = load_interview_preparation_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="applied",
        context_service=_ContextService(_context()),
        preparation_service=_ContextService(forged),
        details_repository=_Repository(),
        feedback_repository=_Repository(),
    )
    assert not result.visible
    assert result.error_message
    assert "signature" not in result.error_message.casefold()


def test_terminal_lifecycle_never_reads_or_renders_interview_data():
    class NeverRead:
        def build(self, *_args):
            raise AssertionError("terminal lifecycle must not read interview data")

        def get(self, *_args):
            raise AssertionError("terminal lifecycle must not read interview data")

    result = load_interview_preparation_view(
        candidate_id="candidate-a",
        job_id="job-1",
        lifecycle_status="offer",
        context_service=NeverRead(),
        preparation_service=NeverRead(),
        details_repository=NeverRead(),
        feedback_repository=NeverRead(),
    )
    assert not result.visible


def test_sprint_12_has_no_ai_or_generator_execution_path():
    files = [
        *ROOT.glob("models/interview_*.py"),
        *ROOT.glob("services/interview_*.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in files).casefold()
    assert "openai" not in source
    assert "requests." not in source
    assert ".generate(" not in source
    assert "llm" not in source


def test_interview_table_writes_are_confined_to_repositories_and_schema():
    allowed = {
        ROOT / "services" / "database.py",
        ROOT / "services" / "interview_details_repository.py",
        ROOT / "services" / "interview_feedback_repository.py",
    }
    offenders = []
    for directory in (ROOT / "services", ROOT):
        paths = directory.glob("*.py")
        for path in paths:
            if path in allowed:
                continue
            source = path.read_text(encoding="utf-8", errors="ignore").casefold()
            if any(
                token in source
                for token in (
                    "insert into candidate_interview_",
                    "update candidate_interview_",
                    "delete from candidate_interview_",
                )
            ):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_sprint_12_does_not_write_career_evidence():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "services").glob("interview_*.py")
    ).casefold()
    assert "career_evidence_repository" not in source
    assert ".save_evidence(" not in source
