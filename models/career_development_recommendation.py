from dataclasses import dataclass, field


@dataclass
class CareerDevelopmentPriority:
    area: str = ""
    why_it_matters: str = ""
    evidence: list[str] = field(
        default_factory=list
    )
    priority: str = ""
    suggested_action: str = ""


@dataclass
class CareerDevelopmentRecommendation:
    current_position: str = ""

    top_development_priorities: list[
        CareerDevelopmentPriority
    ] = field(
        default_factory=list
    )

    strengths_to_leverage: list[str] = field(
        default_factory=list
    )

    market_patterns: list[str] = field(
        default_factory=list
    )

    application_patterns: list[str] = field(
        default_factory=list
    )

    next_best_moves: list[str] = field(
        default_factory=list
    )

    data_confidence: str = ""
