import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
from threading import Barrier
from unittest.mock import Mock

import pytest

from models.candidate import Candidate
from models.candidate_past import (
    CandidateInput, CandidatePast, Certification, Education, Experience, ProfessionalFact,
)
from models.candidate_present import CandidatePresent, CandidateSkill, ProfessionalFactRef
from models.candidate_future import CandidateFuture
from models.candidate_priorities import CandidatePriorities, Priority, PriorityEffect
from models.candidate_profile_snapshot import CandidateProfileSnapshot
from models.professional_ontology import Skill, SkillLevel
from services import database
from services import candidate_profile_repository as module
from services.candidate_repository import CandidateRepository
from services.candidate_profile_repository import CandidateProfileRepository, CandidateProfileVersionConflict


def snapshot(candidate_id="a", version=1):
    return CandidateProfileSnapshot(candidate_id, version, CandidatePast(), CandidatePresent(),
                                    CandidateFuture(), CandidatePriorities())


def complete():
    past = CandidatePast(
        experiences=(Experience("e", "Company", "Analyst", "2020", None,
            (CandidateInput("i", "  I used SQL.\nOriginal wording.  "),),
            (ProfessionalFact("f", "Used SQL.", "i"),)),),
        education=(Education("ed", "College", "Diploma", "Data", "2018-09", "2019", "completed",
            (CandidateInput("ei", "Built a project."),),
            (ProfessionalFact("ef", "Built a project.", "ei"),)),),
        certifications=(Certification("cert", "Certificate", "Issuer", "2019", None, "declared"),),
    )
    present = CandidatePresent(tuple(CandidateSkill(
        Skill("skill-" + level.value, "SQL", "Data", "Querying"), level,
        (ProfessionalFactRef("f"), ProfessionalFactRef("ef")),
    ) for level in SkillLevel), "Ireland", "Dublin", ("English", "Portuguese"))
    priorities = CandidatePriorities(tuple(
        Priority(str(index), "declared-subject", "declared-operator", value, effect)
        for index, (value, effect) in enumerate([
            ("Remote", PriorityEffect.PREFER), (50000, PriorityEffect.DEPRIORITIZE),
            (1.5, PriorityEffect.PREFER), (False, PriorityEffect.EXCLUDE),
        ])
    ))
    return replace(snapshot(), past=past, present=present,
                   future=CandidateFuture(" Data ", "Data Engineer"), priorities=priorities)


@pytest.fixture
def repo():
    for cid in ("a", "b"):
        CandidateRepository().save(Candidate(cid, "Synthetic", "", "", ""))
    return CandidateProfileRepository()


def test_no_snapshot_is_none(repo):
    assert repo.current_candidate("a") is None
    assert repo.current_candidate("missing") is None
    assert repo.candidate_version("a", 1) is None


def test_complete_snapshot_round_trip(repo):
    original = complete()
    assert repo.save_candidate(original) is None
    loaded = repo.current_candidate("a")
    assert loaded == original
    assert repo.candidate_version("a", 1) == original
    assert isinstance(loaded.past.experiences[0].inputs[0], CandidateInput)
    assert isinstance(loaded.past.education[0].facts[0], ProfessionalFact)
    assert isinstance(loaded.past.certifications[0], Certification)
    assert all(isinstance(skill.level, SkillLevel) for skill in loaded.present.skills)
    assert all(isinstance(skill.skill, Skill) for skill in loaded.present.skills)
    assert loaded.present.skills[0].level is SkillLevel.UNKNOWN
    assert [type(p.value) for p in loaded.priorities.priorities] == [str, int, float, bool]
    assert all(isinstance(p.effect, PriorityEffect) for p in loaded.priorities.priorities)
    with database.get_connection() as connection:
        row = connection.execute("SELECT * FROM candidate_profile_v2_snapshots").fetchone()
    assert row["created_at"]
    assert set(json.loads(row["profile_json"])) == set(asdict(original))
    assert "created_at" not in json.loads(row["profile_json"])


def test_empty_branches_round_trip_without_inventing_state(repo):
    original = snapshot()
    repo.save_candidate(original)
    assert repo.current_candidate("a") == original
    assert repo.current_candidate("a").future.target_role is None


def test_sequential_versions_and_candidate_histories(repo):
    versions = [replace(complete(), version=n, future=CandidateFuture(target_role=f"Role {n}"))
                for n in (1, 2, 3)]
    repo.save_candidate(snapshot("b"))
    for item in versions:
        repo.save_candidate(item)
        assert repo.current_candidate("a") == item
    for item in versions:
        assert repo.candidate_version("a", item.version) == item
    assert repo.current_candidate("b") == snapshot("b")
    assert repo.candidate_version("b", 2) is None
    assert repo.candidate_version("a", 4) is None


@pytest.mark.parametrize("saved,requested", [
    (0, 2), (0, 3), (1, 3), (1, 1), (2, 1), (2, 2), (2, 4),
])
def test_rejects_nonsequential_or_replacement_versions(repo, saved, requested):
    for version in range(1, saved + 1):
        repo.save_candidate(snapshot(version=version))
    with pytest.raises(CandidateProfileVersionConflict):
        repo.save_candidate(replace(snapshot(version=requested), future=CandidateFuture("Replacement")))
    assert repo.current_candidate("a") == (snapshot(version=saved) if saved else None)
    for version in range(1, saved + 1):
        assert repo.candidate_version("a", version) == snapshot(version=version)


def test_exact_duplicate_also_rejected(repo):
    item = snapshot()
    repo.save_candidate(item)
    with pytest.raises(CandidateProfileVersionConflict):
        repo.save_candidate(item)


def test_zero_version_is_rejected_by_domain_and_schema(repo):
    with pytest.raises(ValueError):
        snapshot(version=0)
    with pytest.raises(sqlite3.IntegrityError):
        with database.get_connection() as connection:
            connection.execute("""INSERT INTO candidate_profile_v2_snapshots
                VALUES (?, ?, ?, ?)""", ("a", 0, "{}", database.utc_now()))
    assert repo.current_candidate("a") is None


def test_candidate_fk_and_cascade(repo):
    with pytest.raises(ValueError, match="Candidate does not exist"):
        repo.save_candidate(snapshot("missing"))
    repo.save_candidate(snapshot())
    repo.save_candidate(snapshot("b"))
    with database.get_connection() as connection:
        connection.execute("DELETE FROM candidates WHERE id = ?", ("a",))
    assert repo.current_candidate("a") is None
    assert repo.current_candidate("b") == snapshot("b")


@pytest.mark.parametrize("current", [0, 1])
def test_concurrent_same_next_version_has_one_winner(repo, monkeypatch, current):
    if current:
        repo.save_candidate(snapshot())
    original_connection = module.get_connection
    barrier = Barrier(2)
    @contextmanager
    def synchronized_connection():
        with original_connection() as connection:
            barrier.wait(timeout=10)
            yield connection
    monkeypatch.setattr(module, "get_connection", synchronized_connection)
    def save(target):
        try:
            repo.save_candidate(target)
            return "saved"
        except CandidateProfileVersionConflict:
            return "conflict"
    variants = [replace(snapshot(version=current + 1), future=CandidateFuture(target_role=role))
                for role in ("First", "Second")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(save, variants))
    assert sorted(outcomes) == ["conflict", "saved"]
    monkeypatch.setattr(module, "get_connection", original_connection)
    assert repo.current_candidate("a") == variants[outcomes.index("saved")]
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) AS n FROM candidate_profile_v2_snapshots").fetchone()["n"] == current + 1


def test_failure_rolls_back_insert_and_allows_retry(repo, monkeypatch):
    original_connection = module.get_connection
    @contextmanager
    def failing_connection():
        with original_connection() as connection:
            yield connection
            raise RuntimeError("Injected before commit")
    with monkeypatch.context() as scoped:
        scoped.setattr(module, "get_connection", failing_connection)
        with pytest.raises(RuntimeError, match="Injected"):
            repo.save_candidate(snapshot())
    assert repo.current_candidate("a") is None
    repo.save_candidate(snapshot())
    assert repo.current_candidate("a") == snapshot()


@pytest.mark.parametrize("corruption", ["fact", "skill", "priority", "identity", "version", "array"])
def test_read_uses_domain_constructors_and_checks_storage_identity(repo, corruption):
    repo.save_candidate(complete())
    with database.get_connection() as connection:
        payload = json.loads(connection.execute(
            "SELECT profile_json FROM candidate_profile_v2_snapshots").fetchone()["profile_json"])
        if corruption == "fact":
            payload["past"]["experiences"][0]["facts"][0]["candidate_input_id"] = "missing"
        elif corruption == "skill":
            payload["present"]["skills"][0]["evidence_refs"][0]["fact_id"] = "missing"
        elif corruption == "priority":
            payload["priorities"]["priorities"][0]["effect"] = "unsupported"
        elif corruption == "identity":
            payload["candidate_id"] = "b"
        elif corruption == "version":
            payload["version"] = 2
        else:
            payload["present"]["languages"] = "English"
        connection.execute("UPDATE candidate_profile_v2_snapshots SET profile_json = ?", (json.dumps(payload),))
    with pytest.raises((TypeError, ValueError)):
        repo.current_candidate("a")


def test_legacy_and_cpv2_never_cross_read(repo):
    from services.profile_snapshot_repository import ProfileSnapshotRepository
    from tests.test_profile_interpretation_architecture import profiles
    legacy = ProfileSnapshotRepository()
    original, _, _ = profiles()
    original = replace(original, candidate_id="a")
    legacy.save_candidate(original)
    assert repo.current_candidate("a") is None
    assert repo.candidate_version("a", 1) is None
    repo.save_candidate(snapshot())
    repo.save_candidate(snapshot(version=2))
    assert legacy.current_candidate("a") == original
    assert legacy.candidate_version("a", 2) is None
    repo.save_candidate(snapshot("b"))
    assert legacy.current_candidate("b") is None
    with pytest.raises(TypeError):
        repo.save_candidate(original)


def test_no_producer_dependencies_or_bootstrap_on_reads(repo, monkeypatch):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == {
        "dataclasses", "enum", "models.candidate_profile_snapshot", "models.candidate_past",
        "models.candidate_present", "models.candidate_future", "models.candidate_priorities",
        "models.professional_ontology", "services.database",
    }
    forbidden = Mock(side_effect=AssertionError("No bootstrap or interpretation"))
    monkeypatch.setattr(database, "initialize_database", forbidden)
    repo.save_candidate(snapshot())
    assert CandidateProfileRepository().current_candidate("a") == snapshot()
    forbidden.assert_not_called()
    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden_name in ("onboarding", "memory_signature", "source_signature", "readiness", "candidate_profile_snapshots"):
        assert forbidden_name not in source


def test_schema_is_additive_idempotent_and_minimal(repo):
    repo.save_candidate(snapshot())
    with database.get_connection() as connection:
        database.create_candidate_profile_schema(connection)
        database.create_candidate_profile_schema(connection)
        columns = connection.execute("PRAGMA table_info(candidate_profile_v2_snapshots)").fetchall()
        assert [row["name"] for row in columns] == ["candidate_id", "version", "profile_json", "created_at"]
        assert [row["name"] for row in columns if row["pk"]] == ["candidate_id", "version"]
        fk = connection.execute("PRAGMA foreign_key_list(candidate_profile_v2_snapshots)").fetchone()
        assert (fk["table"], fk["from"], fk["to"], fk["on_delete"]) == ("candidates", "candidate_id", "id", "CASCADE")
        index = connection.execute("PRAGMA index_xinfo(idx_candidate_profile_v2_current)").fetchall()
        assert [(row["name"], row["desc"]) for row in index if row["key"]] == [("candidate_id", 0), ("version", 1)]
    assert repo.current_candidate("a") == snapshot()


def test_postgres_schema_uses_existing_server_only_protection(monkeypatch):
    connection = Mock()
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    database.create_candidate_profile_schema(connection)
    sql = "\n".join(call.args[0] for call in connection.execute.call_args_list)
    assert "CREATE TABLE IF NOT EXISTS candidate_profile_v2_snapshots" in sql
    assert "PRIMARY KEY (candidate_id, version)" in sql
    assert "REFERENCES candidates(id) ON DELETE CASCADE" in sql
    assert "ON candidate_profile_v2_snapshots(candidate_id, version DESC)" in sql
    assert "ALTER TABLE candidate_profile_v2_snapshots ENABLE ROW LEVEL SECURITY" in sql
    for role in ("PUBLIC", "anon", "authenticated"):
        assert f"REVOKE ALL ON TABLE candidate_profile_v2_snapshots FROM {role}" in sql
    assert "DROP" not in sql and "GRANT" not in sql


def test_postgres_write_locks_candidate_before_sequence_and_insert(monkeypatch):
    connection = Mock()
    connection.execute.return_value.fetchone.side_effect = [{"id": "a"}, {"version": 1}]
    @contextmanager
    def get_connection():
        yield database.PostgresConnectionAdapter(connection)
    monkeypatch.setattr(module, "get_connection", get_connection)
    monkeypatch.setattr(module, "is_postgres", lambda: True)
    CandidateProfileRepository().save_candidate(snapshot(version=2))
    calls = connection.execute.call_args_list
    assert calls[0].args == ("SELECT id FROM candidates WHERE id = %s FOR UPDATE", ("a",))
    assert "MAX(version)" in calls[1].args[0]
    assert "INSERT INTO candidate_profile_v2_snapshots" in calls[2].args[0]
    assert "?" not in calls[2].args[0]
    assert calls[2].args[1][:2] == ("a", 2)
