from dataclasses import dataclass, field

from models.professional_experience_profile import (
    ProfessionalExperienceProfile,
)


@dataclass
class CandidateProfile:
    current_roles: list[str] = field(
        default_factory=list
    )

    bridge_roles: list[str] = field(
        default_factory=list
    )

    target_roles: list[str] = field(
        default_factory=list
    )

    current_skills: list[str] = field(
        default_factory=list
    )

    growth_skills: list[str] = field(
        default_factory=list
    )

    current_level: str = ""
    professional_summary: str = ""
    job_search_urgency: str = "balanced"

    professional_experiences: list[
        ProfessionalExperienceProfile
    ] = field(
        default_factory=list
    )

    proven_capabilities: list[str] = field(
        default_factory=list
    )

    transferable_capabilities: list[str] = field(
        default_factory=list
    )

    developing_capabilities: list[str] = field(
        default_factory=list
    )

    technical_tools: list[str] = field(
        default_factory=list
    )

    domain_experience: list[str] = field(
        default_factory=list
    )

    competitive_role_families: list[str] = field(
        default_factory=list
    )

    bridge_role_families: list[str] = field(
        default_factory=list
    )

    target_role_families: list[str] = field(
        default_factory=list
    )

    strengths: list[str] = field(
        default_factory=list
    )

    positive_preferences: list[str] = field(
        default_factory=list
    )

    negative_preferences: list[str] = field(
        default_factory=list
    )

    hard_constraints: list[str] = field(
        default_factory=list
    )

    positive_priorities: list[str] = field(
        default_factory=list
    )

    negative_priorities: list[str] = field(
        default_factory=list
    )

    relocation_policy: str = ""
    salary_policy: str = ""

    spoken_languages: list[str] = field(
        default_factory=list
    )
