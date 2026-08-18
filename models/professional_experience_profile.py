from dataclasses import dataclass, field


@dataclass
class ProfessionalExperienceProfile:
    source_experience_id: str = ""

    company: str = ""

    stated_role: str = ""
    inferred_role: str = ""
    role_family: str = ""

    summary: str = ""

    responsibilities: list[str] = field(
        default_factory=list
    )

    demonstrated_capabilities: list[str] = field(
        default_factory=list
    )

    transferable_capabilities: list[str] = field(
        default_factory=list
    )

    tools: list[str] = field(
        default_factory=list
    )

    domains: list[str] = field(
        default_factory=list
    )

    evidence: list[str] = field(
        default_factory=list
    )
