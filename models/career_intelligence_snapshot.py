from dataclasses import dataclass, field

from models.current_market_position import CurrentMarketPosition
from models.gap_and_leverage import LeverageOpportunity, RecurringBlocker
from models.improvement_plan import ImprovementPriority


@dataclass(frozen=True)
class CompetitiveAdvantage:
    signal: str
    evidence_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    evidence_count: int = 0
    affected_role_families: list[str] = field(default_factory=list)
    direction_relevance: str = "unknown"
    confidence: str = "low"


@dataclass(frozen=True)
class DirectionAlignment:
    competitive_now: list[str] = field(default_factory=list)
    bridge: list[str] = field(default_factory=list)
    target: list[str] = field(default_factory=list)
    competitive_target_overlap: list[str] = field(default_factory=list)
    distance_signals: list[str] = field(default_factory=list)
    direction_known: bool = False
    alignment_state: str = "direction_unknown"


@dataclass(frozen=True)
class CareerIntelligenceSnapshot:
    candidate_id: str
    objective_id: str
    schema_version: str
    generated_at: str
    source_signature: str
    current_market_position: CurrentMarketPosition
    competitive_advantages: list[CompetitiveAdvantage] = field(
        default_factory=list
    )
    recurring_blockers: list[RecurringBlocker] = field(default_factory=list)
    leverage_opportunities: list[LeverageOpportunity] = field(
        default_factory=list
    )
    direction_alignment: DirectionAlignment = field(
        default_factory=DirectionAlignment
    )
    improvement_priorities: list[ImprovementPriority] = field(
        default_factory=list
    )
    checkpoint_summary: str = ""
    checkpoint_authority: str = "derived_decision_support"

