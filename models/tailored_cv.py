from dataclasses import dataclass, field


@dataclass
class TailoredCVExperience:
    source_experience_id: str = ""
    company: str = ""
    role: str = ""
    tailored_bullets: list[str] = field(
        default_factory=list
    )


@dataclass
class TailoredCV:
    headline: str = ""
    professional_summary: str = ""

    key_skills: list[str] = field(
        default_factory=list
    )

    experiences: list[
        TailoredCVExperience
    ] = field(
        default_factory=list
    )

    additional_relevant_information: list[str] = field(
        default_factory=list
    )
