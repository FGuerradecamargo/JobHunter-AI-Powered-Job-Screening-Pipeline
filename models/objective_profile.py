from dataclasses import dataclass, field

from models.professional_experience_profile import (
    ProfessionalExperienceProfile,
)


@dataclass
class ObjectiveProfile:
    candidate_id: str
    objective_id: str

    objective_title: str = ""
    objective_description: str = ""

    competitive_role_families: list[str] = field(
        default_factory=list
    )

    bridge_role_families: list[str] = field(
        default_factory=list
    )

    target_role_families: list[str] = field(
        default_factory=list
    )

    relevant_proven_capabilities: list[str] = field(
        default_factory=list
    )

    relevant_transferable_capabilities: list[str] = field(
        default_factory=list
    )

    relevant_developing_capabilities: list[str] = field(
        default_factory=list
    )

    relevant_tools: list[str] = field(
        default_factory=list
    )

    relevant_domains: list[str] = field(
        default_factory=list
    )

    relevant_strengths: list[str] = field(
        default_factory=list
    )

    relevant_experiences: list[
        ProfessionalExperienceProfile
    ] = field(
        default_factory=list
    )

    development_gaps: list[str] = field(
        default_factory=list
    )

    development_priorities: list[str] = field(
        default_factory=list
    )
