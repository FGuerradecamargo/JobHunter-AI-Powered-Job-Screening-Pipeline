from dataclasses import dataclass, field

from models.candidate_constraints import CandidateConstraints
from models.candidate_preferences import CandidatePreferences
from models.candidate_priority import CandidatePriority


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

    preferences: CandidatePreferences = field(
        default_factory=CandidatePreferences
    )

    constraints: CandidateConstraints = field(
        default_factory=CandidateConstraints
    )

    priorities: list[CandidatePriority] = field(
        default_factory=list
    )
