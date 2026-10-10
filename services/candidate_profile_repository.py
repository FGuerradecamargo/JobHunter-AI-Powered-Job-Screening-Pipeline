"""Materialized CPV2 history, independent of its producing workflows."""
from dataclasses import asdict
from enum import Enum
import json

from models.candidate_profile_snapshot import CandidateProfileSnapshot
from models.candidate_past import (
    CandidateInput, CandidatePast, Certification, Education, Experience, ProfessionalFact,
)
from models.candidate_present import CandidatePresent, CandidateSkill, ProfessionalFactRef
from models.candidate_future import CandidateFuture
from models.candidate_priorities import CandidatePriorities, Priority, PriorityEffect
from models.professional_ontology import Skill, SkillLevel
from services.database import get_connection, is_postgres, utc_now


class CandidateProfileVersionConflict(ValueError):
    """The supplied version is not the next version in this candidate's history."""


def _enum_value(value):
    if isinstance(value, Enum):
        return value.value
    raise TypeError("Unsupported snapshot value.")


def _items(value):
    if type(value) is not list:
        raise TypeError("Snapshot collections must be JSON arrays.")
    return value


def _past_entity(kind, item):
    return kind(**{
        **item,
        "inputs": tuple(CandidateInput(**value) for value in _items(item["inputs"])),
        "facts": tuple(ProfessionalFact(**value) for value in _items(item["facts"])),
    })


def _from_json(payload: str) -> CandidateProfileSnapshot:
    data = json.loads(payload)
    past, present, priorities = data["past"], data["present"], data["priorities"]
    return CandidateProfileSnapshot(**{
        **data,
        "past": CandidatePast(**{
            **past,
            "experiences": tuple(_past_entity(Experience, item) for item in _items(past["experiences"])),
            "education": tuple(_past_entity(Education, item) for item in _items(past["education"])),
            "certifications": tuple(Certification(**item) for item in _items(past["certifications"])),
        }),
        "present": CandidatePresent(**{
            **present,
            "skills": tuple(CandidateSkill(**{
                **item,
                "skill": Skill(**item["skill"]),
                "level": SkillLevel(item["level"]),
                "evidence_refs": tuple(ProfessionalFactRef(**ref) for ref in _items(item["evidence_refs"])),
            }) for item in _items(present["skills"])),
            "languages": tuple(_items(present["languages"])),
        }),
        "future": CandidateFuture(**data["future"]),
        "priorities": CandidatePriorities(**{
            **priorities,
            "priorities": tuple(Priority(**{
                **item, "effect": PriorityEffect(item["effect"]),
            }) for item in _items(priorities["priorities"])),
        }),
    })


def _snapshot(row) -> CandidateProfileSnapshot | None:
    if row is None:
        return None
    snapshot = _from_json(row["profile_json"])
    if snapshot.candidate_id != row["candidate_id"] or snapshot.version != row["version"]:
        raise ValueError("Snapshot identity does not match its stored identity.")
    return snapshot


class CandidateProfileRepository:
    def current_candidate(self, candidate_id: str) -> CandidateProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT candidate_id, version, profile_json FROM candidate_profile_v2_snapshots
                   WHERE candidate_id = ? ORDER BY version DESC LIMIT 1""",
                (candidate_id,),
            ).fetchone()
        return _snapshot(row)

    def candidate_version(self, candidate_id: str, version: int) -> CandidateProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT candidate_id, version, profile_json FROM candidate_profile_v2_snapshots
                   WHERE candidate_id = ? AND version = ?""",
                (candidate_id, version),
            ).fetchone()
        return _snapshot(row)

    def save_candidate(self, snapshot: CandidateProfileSnapshot) -> None:
        if type(snapshot) is not CandidateProfileSnapshot:
            raise TypeError("Expected a CPV2 CandidateProfileSnapshot.")
        payload = json.dumps(asdict(snapshot), default=_enum_value, ensure_ascii=False, allow_nan=False)
        with get_connection() as connection:
            # Lock before reading the sequence, including the first-ever snapshot.
            if is_postgres():
                candidate = connection.execute(
                    "SELECT id FROM candidates WHERE id = ? FOR UPDATE", (snapshot.candidate_id,),
                ).fetchone()
            else:
                connection.execute("BEGIN IMMEDIATE")
                candidate = connection.execute(
                    "SELECT id FROM candidates WHERE id = ?", (snapshot.candidate_id,),
                ).fetchone()
            if candidate is None:
                raise ValueError("Candidate does not exist.")
            row = connection.execute(
                """SELECT MAX(version) AS version FROM candidate_profile_v2_snapshots
                   WHERE candidate_id = ?""", (snapshot.candidate_id,),
            ).fetchone()
            if snapshot.version != (row["version"] or 0) + 1:
                raise CandidateProfileVersionConflict("Snapshot must be the next sequential version.")
            connection.execute(
                """INSERT INTO candidate_profile_v2_snapshots
                   (candidate_id, version, profile_json, created_at) VALUES (?, ?, ?, ?)""",
                (snapshot.candidate_id, snapshot.version, payload, utc_now()),
            )
