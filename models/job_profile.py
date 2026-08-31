from dataclasses import dataclass, field


@dataclass
class JobProfile:
    job_id: str

    canonical_role: str = ""
    role_family: str = ""
    seniority: str = ""
    core_mission: str = ""

    must_have_capabilities: list[str] = field(default_factory=list)
    must_have_experience: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)

    key_responsibilities: list[str] = field(default_factory=list)
    tools_and_technologies: list[str] = field(default_factory=list)
    required_qualifications: list[str] = field(default_factory=list)
    stakeholders_and_collaboration: list[str] = field(default_factory=list)

    domain: str = ""
    expected_autonomy: str = ""

    structural_requirements: list[str] = field(default_factory=list)
    work_conditions: list[str] = field(default_factory=list)
    important_details: list[str] = field(default_factory=list)

    role_context: str = ""
    summary: str = ""
