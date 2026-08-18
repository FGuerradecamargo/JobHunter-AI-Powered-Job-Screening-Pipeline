from dataclasses import dataclass, field

from models.candidate_constraints import CandidateConstraints
from models.candidate_preferences import CandidatePreferences
from models.candidate_priority import CandidatePriority
from models.professional_experience_profile import (
    ProfessionalExperienceProfile,
)


@dataclass
class Candidate:
    id: str
    name: str

    current_role: str
    current_level: str

    professional_summary: str

    target_roles: list[str] = field(
        default_factory=list
    )

    spoken_languages: list[str] = field(
        default_factory=list
    )

    skills: list[str] = field(
        default_factory=list
    )

    strengths: list[str] = field(
        default_factory=list
    )

    development_areas: list[str] = field(
        default_factory=list
    )

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

    preferences: CandidatePreferences = field(
        default_factory=CandidatePreferences
    )

    constraints: CandidateConstraints = field(
        default_factory=CandidateConstraints
    )

    priorities: list[CandidatePriority] = field(
        default_factory=list
    )
