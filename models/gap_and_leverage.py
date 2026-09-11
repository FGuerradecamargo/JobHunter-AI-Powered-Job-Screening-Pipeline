from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecurringBlocker:
    blocker: str
    gap_type: str = "observed_blocker"
    evidence_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    evidence_count: int = 0
    independent_sources: int = 0
    affected_role_families: list[str] = field(default_factory=list)
    direction_relevance: str = "unknown"
    confidence: str = "low"


@dataclass(frozen=True)
class LeverageOpportunity:
    action: str
    rationale: str
    expected_best_match_impact: str
    evidence_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    affected_role_families: list[str] = field(default_factory=list)
    direction_relevance: str = "unknown"
    leverage_type: str = "evidence_development"
    confidence: str = "low"


@dataclass(frozen=True)
class MarketLeverageStrength:
    strength: str
    evidence_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    affected_role_families: list[str] = field(default_factory=list)
    direction_relevance: str = "unknown"
    confidence: str = "low"


@dataclass(frozen=True)
class GapAndLeverageAssessment:
    candidate_id: str
    recurring_blockers: list[RecurringBlocker] = field(default_factory=list)
    leverage_opportunities: list[LeverageOpportunity] = field(default_factory=list)
    market_strengths: list[MarketLeverageStrength] = field(default_factory=list)
    target_role_families: list[str] = field(default_factory=list)
    direction_known: bool = False
