from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


MARKET_PROFILE_SCHEMA_VERSION = "market-profile-v1"


class MarketConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())


def _items(values) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                _clean(value)
                for value in values or ()
                if _clean(value)
            },
            key=str.casefold,
        )
    )


@dataclass(frozen=True)
class MarketSegment:
    """
    Global market segment.

    Empty fields mean "not constrained by this dimension"; they never mean a
    candidate preference.
    """
    role_family: str = ""
    location: str = ""
    seniority: str = ""
    domain: str = ""
    time_window: str = ""

    def __post_init__(self) -> None:
        for name in (
            "role_family",
            "location",
            "seniority",
            "domain",
            "time_window",
        ):
            object.__setattr__(
                self,
                name,
                _clean(getattr(self, name)),
            )


@dataclass(frozen=True)
class MarketJobObservation:
    """
    Candidate-independent projection of one globally observable job.

    Personal Gmail/manual metadata must not be placed in this object.
    """
    job_id: str
    observed_at: str
    source_refs: tuple[str, ...]
    role_family: str = ""
    location: str = ""
    seniority: str = ""
    domain: str = ""
    work_mode: str = ""
    employment_type: str = ""
    capabilities: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    compensation_known: bool = False
    compensation: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", _clean(self.job_id))
        object.__setattr__(self, "observed_at", _clean(self.observed_at))
        object.__setattr__(self, "source_refs", _items(self.source_refs))
        object.__setattr__(self, "capabilities", _items(self.capabilities))
        object.__setattr__(self, "tools", _items(self.tools))
        for name in (
            "role_family",
            "location",
            "seniority",
            "domain",
            "work_mode",
            "employment_type",
        ):
            object.__setattr__(
                self,
                name,
                _clean(getattr(self, name)),
            )
        if not self.job_id or not self.observed_at or not self.source_refs:
            raise ValueError(
                "Market observations require job identity, time and global provenance."
            )
        stamp = datetime.fromisoformat(self.observed_at)
        if stamp.tzinfo is None:
            raise ValueError("Market observation time requires a timezone.")
        if any(not ref.casefold().startswith("public:") for ref in self.source_refs):
            raise ValueError(
                "Private candidate sources cannot enter the global MarketProfile."
            )
        compensation = _clean(self.compensation)
        if self.compensation_known and not compensation:
            raise ValueError("Compensation requires explicit observed evidence.")
        object.__setattr__(self, "compensation", compensation)
        object.__setattr__(self, "compensation_known", bool(compensation))


@dataclass(frozen=True)
class MarketPattern:
    dimension: str
    label: str
    independent_jobs: int
    sample_size: int
    source_job_ids: tuple[str, ...]
    frequency: float
    confidence: MarketConfidence

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension", _clean(self.dimension))
        object.__setattr__(self, "label", _clean(self.label))
        object.__setattr__(self, "source_job_ids", _items(self.source_job_ids))
        if (
            not self.dimension
            or not self.label
            or self.independent_jobs < 1
            or self.sample_size < self.independent_jobs
            or not 0 <= self.frequency <= 1
        ):
            raise ValueError("Invalid market pattern.")


@dataclass(frozen=True)
class MarketProfile:
    profile_version: int
    source_signature: str
    created_at: str
    segment: MarketSegment
    sample_size: int
    patterns: tuple[MarketPattern, ...] = ()
    compensation_observed_count: int = 0
    supersedes_version: int | None = None
    schema_version: str = MARKET_PROFILE_SCHEMA_VERSION
    authority: str = "global_market_evidence"
    uncertainties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.profile_version < 1 or not _clean(self.source_signature):
            raise ValueError(
                "MarketProfile requires a positive version and source signature."
            )
        if not _clean(self.created_at):
            raise ValueError("MarketProfile timestamp is required.")
        if self.sample_size < 0:
            raise ValueError("MarketProfile sample size cannot be negative.")
        if not 0 <= self.compensation_observed_count <= self.sample_size:
            raise ValueError("Invalid compensation observation count.")
        if self.authority != "global_market_evidence":
            raise ValueError("MarketProfile authority is fixed.")
        if any(item.sample_size != self.sample_size for item in self.patterns):
            raise ValueError(
                "All market patterns must use the profile sample size."
            )
