from __future__ import annotations

from dataclasses import asdict
import json

from models.hiring_case import RequirementImportance, EvidenceRequirement, TemporalRequirement
from models.profile_interpretation import (
    AIJobProfileSnapshot,
    CandidateProfileSnapshot,
    InterpretationAuthority,
    InterpretedJobNeed,
    ProfileCapability,
    ProfileCheckpoint,
)
from services.database import get_connection, initialize_database


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _candidate_from_json(raw: str) -> CandidateProfileSnapshot:
    data = json.loads(raw)
    data["capabilities"] = tuple(
        ProfileCapability(**{
            **item,
            "evidence_refs": tuple(item["evidence_refs"]),
            "contexts": tuple(item.get("contexts", ())),
            "outcomes": tuple(item.get("outcomes", ())),
        })
        for item in data["capabilities"]
    )
    checkpoint = data["checkpoint"]
    data["checkpoint"] = ProfileCheckpoint(**{
        **checkpoint,
        **{
            name: tuple(checkpoint.get(name, ()))
            for name in (
                "proven_strengths", "transferable_strengths", "evidence_missing",
                "confirmed_gaps", "current_direction", "open_questions",
                "changes_since_previous_version", "possible_next_profile_triggers",
            )
        },
    })
    for name in (
        "source_refs", "contexts", "evidence_summaries", "confirmed_gaps",
        "evidence_gaps", "objectives", "preferences",
    ):
        data[name] = tuple(data.get(name, ()))
    return CandidateProfileSnapshot(**data)


def _job_from_json(raw: str) -> AIJobProfileSnapshot:
    data = json.loads(raw)
    data["needs"] = tuple(
        InterpretedJobNeed(
            **{
                **item,
                "importance": RequirementImportance(item["importance"]),
                "authority": InterpretationAuthority(item["authority"]),
                "hard_fact_refs": tuple(item["hard_fact_refs"]),
                "evidence_requirement": EvidenceRequirement(item.get("evidence_requirement", "defensible")),
                "evidence_requirement_refs": tuple(item.get("evidence_requirement_refs", ())),
                "temporal_requirement": TemporalRequirement(item.get("temporal_requirement", "not_required")),
                "temporal_requirement_refs": tuple(item.get("temporal_requirement_refs", ())),
            }
        )
        for item in data["needs"]
    )
    for name in ("responsibilities", "uncertainties", "tools_as_means"):
        data[name] = tuple(data.get(name, ()))
    return AIJobProfileSnapshot(**data)


class ProfileSnapshotRepository:
    def __init__(self) -> None:
        initialize_database()

    def current_candidate(self, candidate_id: str) -> CandidateProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json FROM candidate_profile_snapshots
                   WHERE candidate_id = ? ORDER BY profile_version DESC LIMIT 1""",
                (candidate_id,),
            ).fetchone()
        return _candidate_from_json(row["profile_json"]) if row else None

    def candidate_for_signature(
        self, candidate_id: str, memory_signature: str, schema_version: str,
    ) -> CandidateProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json FROM candidate_profile_snapshots
                   WHERE candidate_id = ? AND memory_signature = ? AND schema_version = ?""",
                (candidate_id, memory_signature, schema_version),
            ).fetchone()
        return _candidate_from_json(row["profile_json"]) if row else None

    def candidate_version(self, candidate_id: str, version: int) -> CandidateProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json FROM candidate_profile_snapshots
                   WHERE candidate_id = ? AND profile_version = ?""",
                (candidate_id, version),
            ).fetchone()
        return _candidate_from_json(row["profile_json"]) if row else None

    def save_candidate(self, profile: CandidateProfileSnapshot) -> None:
        with get_connection() as connection:
            connection.execute(
                """INSERT INTO candidate_profile_snapshots
                   (candidate_id, profile_version, schema_version, memory_signature,
                    supersedes_version, profile_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile.candidate_id, profile.profile_version, profile.schema_version,
                    profile.memory_signature, profile.supersedes_version,
                    _json(asdict(profile)), profile.created_at,
                ),
            )

    def current_job(self, job_id: str) -> AIJobProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json FROM job_profile_snapshots
                   WHERE job_id = ? ORDER BY profile_version DESC LIMIT 1""",
                (job_id,),
            ).fetchone()
        return _job_from_json(row["profile_json"]) if row else None

    def job_for_signature(
        self, job_id: str, job_signature: str, schema_version: str,
    ) -> AIJobProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json FROM job_profile_snapshots
                   WHERE job_id = ? AND job_signature = ? AND schema_version = ?""",
                (job_id, job_signature, schema_version),
            ).fetchone()
        return _job_from_json(row["profile_json"]) if row else None

    def job_version(self, job_id: str, version: int) -> AIJobProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json FROM job_profile_snapshots
                   WHERE job_id = ? AND profile_version = ?""",
                (job_id, version),
            ).fetchone()
        return _job_from_json(row["profile_json"]) if row else None

    def save_job(self, profile: AIJobProfileSnapshot) -> None:
        with get_connection() as connection:
            connection.execute(
                """INSERT INTO job_profile_snapshots
                   (job_id, profile_version, schema_version, job_signature,
                    supersedes_version, profile_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile.job_id, profile.profile_version, profile.schema_version,
                    profile.job_signature, profile.supersedes_version,
                    _json(asdict(profile)), profile.created_at,
                ),
            )
