"""Shared source authority contract for interpretation and persisted provenance."""
from dataclasses import dataclass
from enum import Enum


class SourceRefClass(str, Enum):
    CANDIDATE_EVIDENCE = "candidate_evidence"
    CAREER_MEMORY_SOURCE = "career_memory_source"
    JOB_HARD_FACT = "job_hard_fact"
    DERIVED_CHECKPOINT = "derived_checkpoint"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RegisteredSourceRef:
    ref: str
    source_class: SourceRefClass
    owner_id: str
    source_type: str
    usable_evidence: bool = False
    confirmed_absence_for: tuple[str, ...] = ()
    temporal_need_id: str = ""
    temporal_version: str = ""
    performed_on: str = ""
