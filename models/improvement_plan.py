from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImprovementPriority:
    priority_id: str
    title: str
    category: str
    why_now: str
    related_objective: str = ""
    direction_relevance: str = "unknown"
    affected_role_families: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    confidence: str = "low"
    priority_band: str = "watch"


@dataclass(frozen=True)
class ImprovementPlan:
    candidate_id: str
    priorities: list[ImprovementPriority] = field(default_factory=list)
    related_objective: str = ""
    target_role_families: list[str] = field(default_factory=list)
    direction_known: bool = False
    checkpoint_authority: str = "decision_support"

