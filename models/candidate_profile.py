from dataclasses import dataclass, field


@dataclass
class CandidateProfile:
    current_roles: list[str] = field(default_factory=list)
    bridge_roles: list[str] = field(default_factory=list)
    target_roles: list[str] = field(default_factory=list)

    current_skills: list[str] = field(default_factory=list)
    growth_skills: list[str] = field(default_factory=list)