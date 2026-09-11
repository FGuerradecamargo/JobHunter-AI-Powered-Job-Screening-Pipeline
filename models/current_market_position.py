from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketPositionRoleFamily:
    role_family: str
    authority: str
    evidence_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    independent_sources: int = 0
    sample_size: int = 0
    frequency: float = 0.0
    confidence: str = "low"


@dataclass(frozen=True)
class CurrentMarketPosition:
    candidate_id: str
    competitive_role_families: list[
        MarketPositionRoleFamily
    ] = field(default_factory=list)
    bridge_role_families: list[
        MarketPositionRoleFamily
    ] = field(default_factory=list)
    target_role_families: list[
        MarketPositionRoleFamily
    ] = field(default_factory=list)
    average_fit: float | None = None
    fit_sample_size: int = 0
    best_match_count: int = 0
    near_match_count: int = 0
    sample_size: int = 0

