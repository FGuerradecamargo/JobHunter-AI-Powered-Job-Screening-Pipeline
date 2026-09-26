from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3
import pytest

from services.database import get_connection, create_interview_round_schema
from services.interview_round_repository import InterviewRoundRepository
from services.application_outcome_service import ApplicationOutcomeService
from services.application_outcome_ui import load_application_outcome_view, dispatch_application_outcome_action
from services.application_outcome_repository import ApplicationOutcomeRepository
from services.career_evidence_builder import build_outcome_evidence
from models.application_tracking import (
    ApplicationStage,
    InterviewRound,
    InterviewRoundFeedback,
    TERMINAL_APPLICATION_STAGES,
)


def test_no_response_is_distinct_from_rejected():
    assert ApplicationStage.NO_RESPONSE is not ApplicationStage.REJECTED
    assert ApplicationStage.NO_RESPONSE in TERMINAL_APPLICATION_STAGES
    assert ApplicationStage.REJECTED in TERMINAL_APPLICATION_STAGES


def test_multiple_interview_rounds_are_sequence_based_not_named_final():
    first = InterviewRound(
        interview_id="i1",
        candidate_id="c",
        job_id="j",
        sequence=1,
        scheduled_at="2026-09-28T10:00:00+01:00",
        interviewer_names=("Alex",),
        interviewer_roles=("Recruiter",),
    )
    second = InterviewRound(
        interview_id="i2",
        candidate_id="c",
        job_id="j",
        sequence=2,
        scheduled_at="2026-10-01T14:00:00+01:00",
        interviewer_roles=("Technical lead",),
    )
    assert first.sequence == 1
    assert second.sequence == 2
    assert second.interviewer_names == ()
    assert second.interviewer_roles == ("Technical lead",)


def test_interviewer_name_is_optional_when_role_is_known():
    item = InterviewRound(
        interview_id="i1",
        candidate_id="c",
        job_id="j",
        sequence=1,
        scheduled_at="",
        interviewer_roles=("Head of Operations",),
    )
    assert item.interviewer_names == ()
    assert item.interviewer_roles == ("Head of Operations",)


def test_feedback_can_store_free_text_and_next_steps_without_becoming_candidate_fact():
    feedback = InterviewRoundFeedback(
        interview_id="i1",
        candidate_id="c",
        job_id="j",
        feedback_text="They focused on stakeholder management.",
        next_steps="Technical interview next week.",
    )
    assert "stakeholder" in feedback.feedback_text.lower()
    assert not hasattr(feedback, "candidate_profile_update")


@pytest.fixture
def rounds():
    with get_connection() as con:
        for cid in ("c", "other"):
            con.execute("""INSERT INTO candidates
                (id, name, current_role, current_level, professional_summary, target_roles_json,
                 spoken_languages_json, skills_json, strengths_json, development_areas_json,
                 preferences_json, constraints_json, created_at, updated_at)
                VALUES (?, '', '', '', '', '[]', '[]', '[]', '[]', '[]', '{}', '{}', 'now', 'now')""", (cid,))
        con.execute("INSERT INTO jobs (id, title, created_at, updated_at) VALUES ('j', 'Test role', 'now', 'now')")
        con.execute("""INSERT INTO candidate_job_analyses (candidate_id, job_id, status, created_at, updated_at)
                       VALUES ('c', 'j', 'applied', 'now', 'now')""")
    return InterviewRoundRepository()


def test_rounds_persist_and_retry_is_idempotent(rounds):
    first = rounds.create(candidate_id="c", job_id="j", scheduled_at="", interview_id="request-1", interviewer_roles=("Recruiter",))
    assert rounds.create(candidate_id="c", job_id="j", scheduled_at="", interview_id="request-1", interviewer_roles=("Recruiter",)) == first
    second = rounds.create(candidate_id="c", job_id="j", scheduled_at="", interviewer_roles=("Manager",))
    third = rounds.create(candidate_id="c", job_id="j", scheduled_at="")
    assert [r.sequence for r in rounds.list("c", "j")] == [1, 2, 3]
    assert InterviewRoundRepository().list("c", "j") == [first, second, third]
    with pytest.raises(ValueError):
        rounds.create(candidate_id="c", job_id="j", scheduled_at="", interview_id="request-1", notes="different")


def test_cross_candidate_round_and_feedback_denied(rounds):
    first = rounds.create(candidate_id="c", job_id="j", scheduled_at="")
    assert rounds.list("other", "j") == []
    with pytest.raises(ValueError):
        rounds.create(candidate_id="other", job_id="j", scheduled_at="")
    feedback = InterviewRoundFeedback(first.interview_id, "c", "j", "Source feedback", "Next round")
    saved = rounds.save_feedback(feedback)
    revised = rounds.save_feedback(replace(feedback, next_steps="Updated next step"))
    assert revised.created_at == saved.created_at
    assert rounds.feedback_for(first.interview_id, "c", "j") == revised
    assert rounds.feedback_for(first.interview_id, "other", "j") is None
    with pytest.raises(ValueError):
        rounds.save_feedback(replace(feedback, candidate_id="other"))
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection() as con:
            con.execute("UPDATE candidate_interview_round_feedback SET candidate_id = 'other'")


def test_concurrent_rounds_have_distinct_sequences(rounds):
    def create(_):
        return rounds.create(candidate_id="c", job_id="j", scheduled_at="").sequence
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(create, range(4))) == [1, 2, 3, 4]


def test_no_response_is_terminal_not_rejection_or_candidate_fact(rounds):
    service = ApplicationOutcomeService()
    result = dispatch_application_outcome_action(confirmed=True, action="no_response", candidate_id="c", job_id="j",
        lifecycle_status="applied", service=service)
    assert result.succeeded and result.final_status == "no_response"
    assert service.mark_no_response("c", "j").status == "already_current"
    assert not service.mark_rejected("c", "j").succeeded
    view = load_application_outcome_view(candidate_id="c", job_id="j", lifecycle_status="applied", repository=service.repository)
    assert view.status_label == "No response" and view.is_terminal and view.actions == ()
    evidence = build_outcome_evidence([{"job_id": "j", "final_status": "no_response"}])
    assert evidence[0].statement == "no_response"
    assert evidence[0].metadata["is_employer_rejection"] is False
    assert evidence[0].metadata["outcome_actor"] == "unknown"
    with pytest.raises(ValueError, match="active"):
        rounds.create(candidate_id="c", job_id="j", scheduled_at="")


def test_offer_after_any_interview_not_only_named_final(rounds):
    service = ApplicationOutcomeService()
    assert service.mark_interview("c", "j").succeeded
    assert service.mark_offer("c", "j").succeeded


def test_schedule_validation_and_unknown_schedule():
    with pytest.raises(ValueError):
        InterviewRound("i", "c", "j", 1, "2026-10-01T10:00:00")
    assert InterviewRound("i", "c", "j", 1, "").scheduled_at == ""


def test_schema_is_idempotent_and_protects_composite_scope(rounds):
    item = rounds.create(candidate_id="c", job_id="j", scheduled_at="")
    with get_connection() as con:
        create_interview_round_schema(con)
        create_interview_round_schema(con)
    assert rounds.list("c", "j") == [item]


def test_historical_interview_rows_are_preserved(rounds):
    with get_connection() as con:
        con.execute("""INSERT INTO candidate_interview_details
            (candidate_id, job_id, interviewer, created_at, updated_at)
            VALUES ('c', 'j', 'Historical interviewer', 'then', 'then')""")
    rounds.create(candidate_id="c", job_id="j", scheduled_at="")
    with get_connection() as con:
        row = con.execute("SELECT interviewer FROM candidate_interview_details WHERE candidate_id = 'c' AND job_id = 'j'").fetchone()
    assert row["interviewer"] == "Historical interviewer"


def test_interview_feedback_retains_source_text_and_does_not_update_candidate(rounds):
    with get_connection() as con:
        before = dict(con.execute("SELECT * FROM candidates WHERE id = 'c'").fetchone())
    item = rounds.create(candidate_id="c", job_id="j", scheduled_at="")
    text = "First answer.\nSecond answer  with original spacing."
    feedback = rounds.save_feedback(InterviewRoundFeedback(item.interview_id, "c", "j", text, "Unknown"))
    assert feedback.feedback_text == text
    with get_connection() as con:
        assert dict(con.execute("SELECT * FROM candidates WHERE id = 'c'").fetchone()) == before


def test_insert_failure_rolls_back_and_next_round_can_retry(rounds, monkeypatch):
    from contextlib import contextmanager
    import services.interview_round_repository as module

    @contextmanager
    def failing_connection():
        with get_connection() as con:
            class Failing:
                def execute(self, sql, params=()):
                    if "INSERT INTO candidate_interview_rounds" in sql:
                        raise RuntimeError("injected write failure")
                    return con.execute(sql, params)
            yield Failing()

    monkeypatch.setattr(module, "get_connection", failing_connection)
    with pytest.raises(RuntimeError):
        rounds.create(candidate_id="c", job_id="j", scheduled_at="")
    monkeypatch.setattr(module, "get_connection", get_connection)
    assert rounds.create(candidate_id="c", job_id="j", scheduled_at="").sequence == 1


def test_postgres_round_schema_has_rls_and_scope_fk(monkeypatch):
    from services import database
    class Recorder:
        def __init__(self):
            self.sql = []
        def execute(self, sql):
            self.sql.append(sql)
    con = Recorder()
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    database.create_interview_round_schema(con)
    sql = "\n".join(con.sql)
    for table in ("candidate_interview_rounds", "candidate_interview_round_feedback"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"REVOKE ALL ON TABLE {table} FROM PUBLIC" in sql
    assert "FOREIGN KEY(interview_id, candidate_id, job_id)" in sql
