from dataclasses import dataclass, field


@dataclass
class CareerObjective:
    id: str
    candidate_id: str

    title: str
    description: str

    active: bool = True

    desired_role_families: list[str] = field(
        default_factory=list
    )

    created_at: str = ""
    updated_at: str = ""
