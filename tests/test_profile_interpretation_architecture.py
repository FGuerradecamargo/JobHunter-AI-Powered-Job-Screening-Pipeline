from __future__ import annotations

from dataclasses import replace

import pytest

from models.candidate import Candidate
from models.hiring_case import (
    OpportunitySignal,
    OpportunitySignalKind,
    OpportunitySignalState,
    RequirementAssessment,
    RequirementEvidenceState,
    RequirementImportance,
)
from models.profile_interpretation import (
    AIJobProfileSnapshot,
    CandidateProfileDraft,
    CandidateProfileSnapshot,
    HardJobFact,
    HiringCaseInterpretation,
    InterpretationAuthority,
    InterpretedJobNeed,
    JobHardFacts,
    JobProfileDraft,
    ProfileCapability,
    ProfileCheckpoint,
    RequirementLink,
    SourceEvidence,
)
from models.job_profile import JobProfile
from services.candidate_repository import CandidateRepository
from services.database import get_connection, utc_now
from services.hiring_case_engine import build_hiring_case
from services.profile_hiring_case_adapter import build_profile_hiring_case_input
from services.profile_interpretation_service import ProfileInterpretationService
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.job_hard_facts import build_job_hard_facts
from services.hiring_case_shadow_service import evaluate_profile_hiring_case_shadow
from services.candidate_profile_source import build_candidate_profile_source_evidence
from services.career_memory_source_builder import CareerMemorySourceSnapshot
from tests.hiring_case_shadow_fixtures import fixture_source


def source(ref="experience:1", summary="Resolved complex payment disputes"):
    return SourceEvidence(ref, "professional_experience", summary)


def checkpoint(**changes):
    values = {
        "current_position": "Experienced operations specialist",
        "proven_strengths": ("Investigation",),
        "open_questions": ("Need a fraud example?",),
    }
    values.update(changes)
    return ProfileCheckpoint(**values)


class FakeRepository:
    def __init__(self):
        self.candidates = []
        self.jobs = []

    def candidate_for_signature(self, candidate_id, signature, schema):
        return next((x for x in self.candidates if x.candidate_id == candidate_id and x.memory_signature == signature and x.schema_version == schema), None)

    def current_candidate(self, candidate_id):
        rows = [x for x in self.candidates if x.candidate_id == candidate_id]
        return max(rows, key=lambda x: x.profile_version) if rows else None

    def save_candidate(self, profile):
        self.candidates.append(profile)

    def job_for_signature(self, job_id, signature, schema):
        return next((x for x in self.jobs if x.job_id == job_id and x.job_signature == signature and x.schema_version == schema), None)

    def current_job(self, job_id):
        rows = [x for x in self.jobs if x.job_id == job_id]
        return max(rows, key=lambda x: x.profile_version) if rows else None

    def save_job(self, profile):
        self.jobs.append(profile)


class FakeInterpreter:
    def __init__(self):
        self.candidate_calls = []
        self.job_calls = []

    def build_candidate_profile(self, *, candidate_id, memory_payload, source_evidence, previous_checkpoint):
        self.candidate_calls.append((memory_payload, source_evidence, previous_checkpoint))
        ref = source_evidence[-1].ref
        changes = () if previous_checkpoint is None else ("New source-backed evidence added",)
        return CandidateProfileDraft(
            capabilities=(ProfileCapability("investigate", "Investigation", (ref,), contexts=("Operations",)),),
            checkpoint=checkpoint(changes_since_previous_version=changes),
            evidence_summaries=(source_evidence[-1].summary,),
            evidence_gaps=() if len(source_evidence) > 1 else ("Fraud investigation",),
            objectives=("Risk operations",),
        )

    def build_job_profile(self, *, hard_facts, previous_profile):
        self.job_calls.append((hard_facts, previous_profile))
        return JobProfileDraft(needs=(InterpretedJobNeed(
            "need-1", "Investigation", RequirementImportance.CORE,
            InterpretationAuthority.EXPLICIT, (hard_facts.fact_refs[0],),
        ),))

    def analyze_hiring_case(self, **kwargs):
        raise AssertionError("Not used by profile construction tests")


def test_same_memory_signature_reuses_candidate_profile():
    repository = FakeRepository()
    interpreter = FakeInterpreter()
    service = ProfileInterpretationService(repository, interpreter)
    first = service.candidate_profile(
        candidate_id="candidate-a", memory_signature="memory-1",
        memory_payload={"facts": ["one"]}, source_evidence=(source(),),
    )
    second = service.candidate_profile(
        candidate_id="candidate-a", memory_signature="memory-1",
        memory_payload={"facts": ["one"]}, source_evidence=(source(),),
    )
    assert second is first
    assert len(interpreter.candidate_calls) == 1


def test_memory_change_creates_v2_and_preserves_v1():
    repository = FakeRepository()
    service = ProfileInterpretationService(repository, FakeInterpreter())
    v1 = service.candidate_profile(
        candidate_id="candidate-a", memory_signature="memory-1",
        memory_payload={}, source_evidence=(source(),),
    )
    frozen_v1 = v1
    v2 = service.candidate_profile(
        candidate_id="candidate-a", memory_signature="memory-2",
        memory_payload={}, source_evidence=(source(), source("experience:2", "Investigated fraud alert")),
    )
    assert (v2.profile_version, v2.supersedes_version) == (2, 1)
    assert repository.candidates[0] == frozen_v1
    assert v2.source_refs == ("experience:1", "experience:2")
    assert not v2.evidence_gaps


def test_checkpoint_cannot_become_evidence_for_next_profile():
    repository = FakeRepository()

    class Malicious(FakeInterpreter):
        def build_candidate_profile(self, **kwargs):
            if kwargs["previous_checkpoint"]:
                return CandidateProfileDraft(
                    capabilities=(ProfileCapability("api", "API troubleshooting", ("checkpoint:v1",)),),
                    checkpoint=checkpoint(),
                )
            return super().build_candidate_profile(**kwargs)

    service = ProfileInterpretationService(repository, Malicious())
    service.candidate_profile(
        candidate_id="candidate-a", memory_signature="m1", memory_payload={}, source_evidence=(source(),),
    )
    with pytest.raises(ValueError, match="source snapshot"):
        service.candidate_profile(
            candidate_id="candidate-a", memory_signature="m2", memory_payload={},
            source_evidence=(source(), source("experience:2")),
        )


def test_source_projection_ignores_checkpoint_and_unreferenced_profile_claims():
    snapshot = CareerMemorySourceSnapshot(
        "candidate-a",
        {
            "candidate": {
                "proven_capabilities": ["Unsupported profile claim"],
                "professional_experiences": [{
                    "source_experience_id": "work-1",
                    "stated_role": "Operations Analyst",
                    "summary": "Investigated payment disputes",
                    "evidence": ["Owned case decisions"],
                }],
            },
            "profile_checkpoint": {"proven_strengths": ["PRIVATE DERIVED CLAIM"]},
        },
        "memory-signature",
    )
    evidence = build_candidate_profile_source_evidence(snapshot)
    assert [item.ref for item in evidence] == ["professional_experience:work-1"]
    assert "Owned case decisions" in evidence[0].summary
    assert "PRIVATE DERIVED CLAIM" not in evidence[0].summary
    assert "Unsupported profile claim" not in evidence[0].summary


def test_same_job_signature_reuses_and_changed_facts_create_v2():
    repository = FakeRepository()
    interpreter = FakeInterpreter()
    service = ProfileInterpretationService(repository, interpreter)
    hard1 = JobHardFacts("job-1", "sig-1", (HardJobFact("f1", "requirement", "Investigation", "job:1"),))
    v1 = service.job_profile(hard_facts=hard1)
    assert service.job_profile(hard_facts=hard1) is v1
    hard2 = JobHardFacts("job-1", "sig-2", (HardJobFact("f2", "requirement", "Fraud investigation", "job:2"),))
    v2 = service.job_profile(hard_facts=hard2)
    assert (v2.profile_version, v2.supersedes_version) == (2, 1)
    assert len(interpreter.job_calls) == 2


def test_job_hard_projection_is_explicit_provenanced_and_content_signed():
    profile = JobProfile(
        "job-1",
        must_have_capabilities=["Fraud investigation"],
        nice_to_have=["SQL"],
        key_responsibilities=["Review suspicious transactions"],
        tools_and_technologies=["Case manager"],
        work_conditions=["hybrid"],
    )
    first = build_job_hard_facts(profile, explicit_blockers=("Irish work authorization",))
    second = build_job_hard_facts(profile, explicit_blockers=("Irish work authorization",))
    changed = build_job_hard_facts(replace(profile, nice_to_have=["Python"]), explicit_blockers=("Irish work authorization",))
    assert first == second
    assert first.job_signature != changed.job_signature
    assert all(item.explicit and item.source_ref.startswith("job:job-1:parsed:") for item in first.facts)
    assert [item.value for item in first.facts if item.hard_blocker] == ["Irish work authorization"]


def test_strongly_implied_need_cannot_create_hard_blocker():
    fact = HardJobFact("f1", "responsibility", "Review payments", "job:1")
    with pytest.raises(ValueError, match="explicit"):
        InterpretedJobNeed(
            "n1", "License", RequirementImportance.CORE,
            InterpretationAuthority.STRONGLY_IMPLIED, (fact.fact_id,), hard_blocker=True,
        )


def profiles(*, confirmed_gaps=()):
    candidate = CandidateProfileSnapshot(
        "candidate-a", 1, "memory", "2026-01-01T00:00:00+00:00", ("experience:1",),
        (ProfileCapability("cap", "Investigation", ("experience:1",)),), checkpoint(),
        confirmed_gaps=confirmed_gaps,
    )
    fact = HardJobFact("f1", "requirement", "Investigation", "job:1")
    hard = JobHardFacts("job-1", "job-sig", (fact,))
    job = AIJobProfileSnapshot(
        "job-1", 1, "job-sig", "2026-01-01T00:00:00+00:00",
        (InterpretedJobNeed("need-1", "Investigation", RequirementImportance.CORE, InterpretationAuthority.EXPLICIT, ("f1",)),),
    )
    return candidate, job, hard


@pytest.mark.parametrize("state", [RequirementEvidenceState.PROVEN, RequirementEvidenceState.TRANSFERABLE])
def test_proven_and_transferable_require_valid_evidence_refs(state):
    candidate, job, hard = profiles()
    interpretation = HiringCaseInterpretation((RequirementLink("need-1", state),))
    result = build_profile_hiring_case_input(
        candidate_profile=candidate, job_profile=job, hard_facts=hard, interpretation=interpretation,
    )
    assert result.requirements[0].evidence_state is RequirementEvidenceState.EVIDENCE_MISSING
    invalid = HiringCaseInterpretation((RequirementLink("need-1", state, ("checkpoint:v1",)),))
    with pytest.raises(ValueError, match="unknown candidate evidence"):
        build_profile_hiring_case_input(
            candidate_profile=candidate, job_profile=job, hard_facts=hard, interpretation=invalid,
        )


def test_unconfirmed_ai_gap_is_missing_but_confirmed_gap_remains_gap():
    candidate, job, hard = profiles()
    link = HiringCaseInterpretation((RequirementLink("need-1", RequirementEvidenceState.GAP),))
    result = build_profile_hiring_case_input(
        candidate_profile=candidate, job_profile=job, hard_facts=hard, interpretation=link,
    )
    assert result.requirements[0].evidence_state is RequirementEvidenceState.EVIDENCE_MISSING
    result = build_profile_hiring_case_input(
        candidate_profile=replace(candidate, confirmed_gaps=("need-1",)),
        job_profile=job, hard_facts=hard, interpretation=link,
    )
    assert result.requirements[0].evidence_state is RequirementEvidenceState.GAP


def test_hard_assessment_beats_ai_and_explicit_blocker_wins():
    candidate, job, hard = profiles()
    hard = replace(hard, facts=hard.facts + (HardJobFact("block", "eligibility", "Required license absent", "job:block", hard_blocker=True),))
    interpretation = HiringCaseInterpretation(
        (RequirementLink("need-1", RequirementEvidenceState.GAP),),
        (OpportunitySignal(OpportunitySignalKind.CAREER_DIRECTION, OpportunitySignalState.POSITIVE, RequirementImportance.CORE),),
    )
    proven = RequirementAssessment(
        "need-1", "Investigation", RequirementImportance.CORE,
        RequirementEvidenceState.PROVEN, ["experience:1"], "Hard direct relationship", True,
    )
    data = build_profile_hiring_case_input(
        candidate_profile=candidate, job_profile=job, hard_facts=hard,
        interpretation=interpretation, hard_assessments=(proven,),
    )
    case = build_hiring_case(data)
    assert data.requirements[0].evidence_state is RequirementEvidenceState.PROVEN
    assert case.classification.value == "ineligible"


def test_snapshot_repository_is_candidate_scoped_and_historical(tmp_path):
    CandidateRepository().save(Candidate("candidate-a", "A", "", "", ""))
    CandidateRepository().save(Candidate("candidate-b", "B", "", "", ""))
    repository = ProfileSnapshotRepository()
    one, _, _ = profiles()
    two = replace(one, profile_version=2, memory_signature="memory-2", supersedes_version=1)
    repository.save_candidate(one)
    repository.save_candidate(two)
    assert repository.current_candidate("candidate-a") == two
    assert repository.candidate_version("candidate-a", 1) == one
    assert repository.current_candidate("candidate-b") is None


def test_job_snapshot_repository_reuses_signature_and_preserves_history():
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO jobs (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("job-1", "Operations Analyst", now, now),
        )
    repository = ProfileSnapshotRepository()
    _, one, _ = profiles()
    two = replace(one, profile_version=2, job_signature="job-sig-2", supersedes_version=1)
    repository.save_job(one)
    repository.save_job(two)
    assert repository.job_for_signature("job-1", "job-sig", one.schema_version) == one
    assert repository.current_job("job-1") == two
    assert repository.job_version("job-1", 1) == one
    assert repository.current_job("other-job") is None


def test_profile_tables_are_server_only_in_postgres_source():
    from pathlib import Path
    source_text = Path("services/database.py").read_text(encoding="utf-8")
    for table in ("candidate_profile_snapshots", "job_profile_snapshots"):
        assert table in source_text
    assert "ENABLE ROW LEVEL SECURITY" in source_text
    assert "FROM anon" in source_text
    assert "FROM authenticated" in source_text


def test_postgres_profile_schema_emits_rls_and_direct_grant_revocation(monkeypatch):
    from services import database

    class RecordingConnection:
        def __init__(self):
            self.queries = []

        def execute(self, query, params=None):
            self.queries.append(query)

    connection = RecordingConnection()
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    database.create_profile_interpretation_schema(connection)
    statements = "\n".join(connection.queries)
    for table in ("candidate_profile_snapshots", "job_profile_snapshots"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"REVOKE ALL ON TABLE {table} FROM PUBLIC" in statements
        assert f"REVOKE ALL ON TABLE {table} FROM anon" in statements
        assert f"REVOKE ALL ON TABLE {table} FROM authenticated" in statements


def test_profile_shadow_is_non_authoritative_content_free_and_preserves_legacy(caplog):
    caplog.set_level("INFO", logger="services.hiring_case_shadow_service")
    legacy_source = fixture_source()
    candidate, job, hard = profiles()
    candidate = replace(
        candidate,
        candidate_id=legacy_source.candidate.id,
        checkpoint=checkpoint(current_position="PRIVATE CHECKPOINT SENTINEL"),
    )
    interpretation = HiringCaseInterpretation((RequirementLink(
        "need-1", RequirementEvidenceState.PROVEN, ("experience:1",),
        "Source-backed relationship", True,
    ),), (
        OpportunitySignal(
            OpportunitySignalKind.CAREER_DIRECTION,
            OpportunitySignalState.POSITIVE,
            RequirementImportance.CORE,
        ),
    ))
    original_recommendation = legacy_source.analysis_source.recommendation
    result = evaluate_profile_hiring_case_shadow(
        legacy_source,
        candidate_profile=candidate,
        job_profile=job,
        hard_facts=hard,
        interpretation=interpretation,
    )
    assert legacy_source.analysis_source.recommendation == original_recommendation
    assert result.authoritative is False
    assert "PRIVATE CHECKPOINT SENTINEL" not in caplog.text
    assert legacy_source.candidate.id not in caplog.text
