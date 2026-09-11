from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CareerEvidence:
    evidence_id: str
    evidence_type: str
    signal_type: str
    source_ref: str
    statement: str

    role_family: str = ""
    observed_at: str = ""
    authority: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )
