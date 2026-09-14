from dataclasses import replace
from contextlib import contextmanager
from pathlib import Path
import sqlite3

import pytest

from models.application_context import PositioningTheme
from models.application_contract import ApplicationEvidenceRef
from models.interview_context import InterviewDetails
from models.interview_prep_contract import InterviewPrepContract
from services.interview_context_builder import build_interview_context
from services.interview_context_service import InterviewContextService
from services.database import create_interview_details_schema
import services.interview_details_repository as details_repository_module
from services.interview_details_repository import InterviewDetailsRepository


def _evidence(ref="e-1", authority="professional_fact", statement="Led operations"):
    return ApplicationEvidenceRef(
        evidence_ref=ref,
        source_type="professional_experience",
        source_id="experience-1",
        authority=authority,
        statement=statement,
    )


def _contract(**changes):
    evidence = [_evidence(), _evidence("e-2", "developing_evidence", "Learning SQL")]
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        application_context_signature="application-context-signature",
        interview_stage="interview",
        application_final_status="",
        eligible=True,
        job_title="Product Operations Specialist",
        company="Example Ltd",
        role_family="Product Operations",
        job_level="Specialist",
        authorized_evidence=evidence,
        development_gaps=["Advanced SQL"],
        protected_structural_gaps=["No production Kubernetes experience"],
        target_requirements=["Process improvement"],
        positioning_themes=[PositioningTheme("Customer operations", ["e-1"])],
        source_signature="prep-contract-signature",
    )
    values.update(changes)
    return InterviewPrepContract(**values)


def _details(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        interview_type="Technical interview",
        interview_format="Video call",
        interviewer="Alex, Engineering Manager",
        duration_minutes=60,
        scheduled_at="2026-09-20T10:00:00+01:00",
        instructions="Prepare a short case study.\nDo not share confidential data.",
        explicit_topics=["SQL", "Stakeholder management"],
    )
    values.update(changes)
    return InterviewDetails(**values)


class ContractService:
    def __init__(self, contract=None):
        self.contract = contract or _contract()
        self.calls = []

    def build(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.contract


class DetailsRepository:
    def __init__(self, details=None):
        self.details = details
        self.calls = []

    def get(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.details

    def save(self, *_args, **_kwargs):
        raise AssertionError("Context read path must not write details.")


def _service(contract=None, details=None):
    return InterviewContextService(
        contract_service=ContractService(contract),
        details_repository=DetailsRepository(details),
    )


@pytest.mark.parametrize("stage", ["interview", "final_interview"])
def test_active_interview_stage_builds_context(stage):
    context = _service(_contract(interview_stage=stage)).build("candidate-a", "job-1")
    assert context.interview_stage == stage
    assert context.job_title == "Product Operations Specialist"


def test_ineligible_lifecycle_cannot_build_active_context():
    with pytest.raises(ValueError, match="active interview"):
        _service(_contract(eligible=False, interview_stage="")).build(
            "candidate-a", "job-1"
        )


def test_context_is_valid_without_optional_details():
    context = _service().build("candidate-a", "job-1")
    assert context.interview_type == ""
    assert context.duration_minutes is None
    assert context.explicit_topics == []


def test_all_supplied_interview_details_are_preserved():
    details = _details()
    context = _service(details=details).build("candidate-a", "job-1")
    assert context.interview_type == details.interview_type
    assert context.interview_format == details.interview_format
    assert context.interviewer == details.interviewer
    assert context.duration_minutes == details.duration_minutes
    assert context.scheduled_at == details.scheduled_at
    assert context.instructions == details.instructions
    assert context.explicit_topics == ["SQL", "Stakeholder management"]


def test_interview_details_never_become_candidate_evidence():
    context = _service(details=_details(explicit_topics=["Rust"])).build(
        "candidate-a", "job-1"
    )
    assert context.explicit_topics == ["Rust"]
    assert context.authorized_evidence == _contract().authorized_evidence
    assert all(item.statement != "Rust" for item in context.authorized_evidence)


def test_final_interview_text_cannot_promote_persisted_stage():
    context = _service(
        _contract(interview_stage="interview"),
        _details(interview_type="Final interview", instructions="Final panel"),
    ).build("candidate-a", "job-1")
    assert context.interview_stage == "interview"


def test_authorized_material_is_exactly_inherited_from_contract():
    contract = _contract()
    context = build_interview_context(contract=contract, details=_details())
    assert context.authorized_evidence == contract.authorized_evidence
    assert context.core_requirements == contract.target_requirements
    assert context.positioning_themes == contract.positioning_themes
    assert context.development_gaps == contract.development_gaps
    assert context.structural_gaps == contract.protected_structural_gaps
    assert context.authorized_evidence[1].authority == "developing_evidence"


@pytest.mark.parametrize(
    "details",
    [_details(candidate_id="candidate-b"), _details(job_id="job-2")],
)
def test_builder_rejects_details_from_another_scope(details):
    with pytest.raises(PermissionError, match="another"):
        build_interview_context(contract=_contract(), details=details)


@pytest.mark.parametrize(
    "contract",
    [_contract(candidate_id="candidate-b"), _contract(job_id="job-2")],
)
def test_service_rejects_contract_from_another_scope(contract):
    with pytest.raises(PermissionError, match="another scope"):
        _service(contract).build("candidate-a", "job-1")


def test_service_rejects_repository_details_from_another_scope():
    with pytest.raises(PermissionError, match="another scope"):
        _service(details=_details(candidate_id="candidate-b")).build(
            "candidate-a", "job-1"
        )


def test_signature_is_deterministic_for_whitespace_case_and_topic_order():
    first = build_interview_context(contract=_contract(), details=_details())
    noisy = _details(
        interview_type="  TECHNICAL   INTERVIEW ",
        interview_format=" video CALL ",
        instructions="  Prepare a short case study.  Do not share confidential data. ",
        explicit_topics=[" stakeholder   MANAGEMENT ", " sql ", "SQL"],
    )
    second = build_interview_context(contract=_contract(), details=noisy)
    assert first.source_signature == second.source_signature


@pytest.mark.parametrize(
    "contract,details",
    [
        (_contract(interview_stage="final_interview"), _details()),
        (_contract(), _details(interview_format="On site")),
        (_contract(), _details(explicit_topics=["Python"])),
        (_contract(), _details(instructions="Bring a presentation")),
    ],
)
def test_stage_or_material_detail_change_changes_signature(contract, details):
    baseline = build_interview_context(contract=_contract(), details=_details())
    changed = build_interview_context(contract=contract, details=details)
    assert baseline.source_signature != changed.source_signature


def test_timestamps_do_not_affect_signature():
    first = build_interview_context(contract=_contract(), details=_details())
    second = build_interview_context(
        contract=_contract(),
        details=replace(_details(), created_at="yesterday", updated_at="today"),
    )
    assert first.source_signature == second.source_signature


def test_read_path_performs_no_lifecycle_outcome_or_detail_writes():
    repository = DetailsRepository(_details())
    service = InterviewContextService(
        contract_service=ContractService(), details_repository=repository
    )
    service.build("candidate-a", "job-1")
    assert repository.calls == [("candidate-a", "job-1")]


def test_prepared_cv_absence_is_irrelevant_and_legacy_prep_is_ignored():
    context = _service().build("candidate-a", "job-1")
    assert context.authorized_evidence
    source = Path("services/interview_context_builder.py").read_text(encoding="utf-8")
    assert "prepared_cv" not in source
    assert "likely_interview_topics" not in source
    assert "strongest_evidence" not in source


def test_interview_context_has_no_ai_api_or_generator_path():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "models/interview_context.py",
            "services/interview_context_builder.py",
            "services/interview_context_service.py",
            "services/interview_details_repository.py",
        )
    ).lower()
    assert "openai" not in source
    assert "llm" not in source
    assert ".generate(" not in source
    assert "requests." not in source


@pytest.fixture
def details_database(tmp_path, monkeypatch):
    database_path = tmp_path / "interview-details.db"

    @contextmanager
    def connection_factory():
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    with connection_factory() as connection:
        connection.execute("CREATE TABLE candidates (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY)")
        connection.execute(
            """
            CREATE TABLE candidate_job_analyses (
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                PRIMARY KEY (candidate_id, job_id)
            )
            """
        )
        connection.executemany(
            "INSERT INTO candidates (id) VALUES (?)",
            [("candidate-a",), ("candidate-b",)],
        )
        connection.executemany(
            "INSERT INTO jobs (id) VALUES (?)", [("job-1",), ("job-2",)]
        )
        connection.execute(
            "INSERT INTO candidate_job_analyses VALUES (?, ?)",
            ("candidate-a", "job-1"),
        )
        create_interview_details_schema(connection)

    monkeypatch.setattr(details_repository_module, "get_connection", connection_factory)
    return InterviewDetailsRepository()


def test_interview_details_repository_round_trip(details_database):
    saved = details_database.save(_details())
    assert saved.interview_type == "Technical interview"
    assert saved.explicit_topics == ["SQL", "Stakeholder management"]
    assert saved.created_at
    assert saved.updated_at


def test_interview_details_repository_updates_same_scoped_record(details_database):
    first = details_database.save(_details())
    second = details_database.save(_details(interview_format="On site"))
    assert second.interview_format == "On site"
    assert second.created_at == first.created_at


def test_interview_details_repository_fails_without_relationship(details_database):
    with pytest.raises(ValueError, match="relationship"):
        details_database.save(_details(candidate_id="candidate-b"))


def test_interview_details_repository_rejects_invalid_duration(details_database):
    with pytest.raises(ValueError, match="positive"):
        details_database.save(_details(duration_minutes=0))
