from dataclasses import dataclass, field


@dataclass
class AIRecommendation:
    job_id: str

    recommendation: str
    competitive_status: str

    current_fit: int
    growth_value: int

    job_level: str = ""
    candidate_level: str = ""
    level_assessment: str = ""

    core_requirements: list[str] = field(default_factory=list)
    requirements_met: list[str] = field(default_factory=list)

    strengths: list[str] = field(default_factory=list)
    development_gaps: list[str] = field(default_factory=list)
    structural_gaps: list[str] = field(default_factory=list)

    positive_points: list[str] = field(default_factory=list)
    personal_negatives: list[str] = field(default_factory=list)
    hard_conflicts: list[str] = field(default_factory=list)

    reason: str = ""
    final_reason: str = ""