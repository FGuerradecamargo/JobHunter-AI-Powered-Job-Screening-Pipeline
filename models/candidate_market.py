from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


CANDIDATE_MARKET_SCHEMA_VERSION = "candidate-market-v1"


class CandidateMarketState(str, Enum):
    PROVEN = "proven"
    TRANSFERABLE = "transferable"
    EVIDENCE_MISSING = "evidence_missing"
    CONFIRMED_GAP = "confirmed_gap"


class ImprovementKind(str, Enum):
    BUILD = "build"
    PROVE = "prove"
    EXPLORE = "explore"


class ImprovementBand(str, Enum):
    NOW = "now"
    NEXT = "next"
    WATCH = "watch"


@dataclass(frozen=True)
class CandidateMarketSignal:
    dimension: str
    label: str
    state: CandidateMarketState
    market_confidence: str
    frequency: float
    source_job_ids: tuple[str, ...] = ()
    candidate_evidence_refs: tuple[str, ...] = ()
    direction_relevance: str = "unknown"


@dataclass(frozen=True)
class CandidateMarketAssessment:
    candidate_id: str
    candidate_profile_version: int
    market_profile_version: int
    market_source_signature: str
    signals: tuple[CandidateMarketSignal, ...] = ()
    direction_known: bool = False
    schema_version: str = CANDIDATE_MARKET_SCHEMA_VERSION
    authority: str = "candidate_market_relationship"
    candidate_memory_signature: str = ""
    evidence_gap_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required.")
        if self.candidate_profile_version < 1 or self.market_profile_version < 1:
            raise ValueError("CandidateMarket requires positive source versions.")
        if not self.market_source_signature:
            raise ValueError("Market source signature is required.")
        if self.authority != "candidate_market_relationship":
            raise ValueError("CandidateMarket authority is fixed.")


@dataclass(frozen=True)
class CandidateImprovement:
    improvement_id: str
    label: str
    kind: ImprovementKind
    band: ImprovementBand
    why: str
    market_confidence: str
    frequency: float
    source_job_ids: tuple[str, ...] = ()
    candidate_evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateImprovementPlan:
    candidate_id: str
    candidate_profile_version: int
    market_profile_version: int
    improvements: tuple[CandidateImprovement, ...] = ()
    authority: str = "decision_support"
    candidate_memory_signature: str = ""
    market_source_signature: str = ""
