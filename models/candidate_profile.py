from dataclasses import dataclass, field


@dataclass
class CandidateProfile:
    current_roles: list[str] = field(default_factory=list)
    bridge_roles: list[str] = field(default_factory=list)
    target_roles: list[str] = field(default_factory=list)

    current_skills: list[str] = field(default_factory=list)
    growth_skills: list[str] = field(default_factory=list)

    current_level: str = ""
    professional_summary: str = ""
    job_search_urgency: str = "balanced"

    positive_preferences: list[str] = field(default_factory=list)
    negative_preferences: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)

    relocation_policy: str = ""
    salary_policy: str = ""

    spoken_languages: list[str] = field(
        default_factory=list
    )