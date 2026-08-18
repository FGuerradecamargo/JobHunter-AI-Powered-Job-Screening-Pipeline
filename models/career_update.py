from dataclasses import dataclass


@dataclass
class CareerUpdate:
    id: str
    candidate_id: str

    update_type: str
    description: str

    created_at: str = ""
