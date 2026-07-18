from dataclasses import dataclass, field


@dataclass
class AIRecommendation:
    job_id: str
    recommendation: str
    current_fit: int
    growth_value: int
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    reason: str = ""