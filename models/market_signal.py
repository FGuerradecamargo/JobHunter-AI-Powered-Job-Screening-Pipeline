from dataclasses import dataclass, field


@dataclass
class MarketSignal:
    role_family: str = ""

    best_match_blockers: list[str] = field(
        default_factory=list
    )

    market_strengths: list[str] = field(
        default_factory=list
    )

    what_would_raise_fit: list[str] = field(
        default_factory=list
    )
