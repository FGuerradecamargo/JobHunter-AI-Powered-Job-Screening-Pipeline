from dataclasses import dataclass, field


@dataclass(frozen=True)
class CareerEvidenceSignal:
    signal_id: str
    signal_type: str
    statement: str

    evidence_refs: list[str] = field(
        default_factory=list
    )
    source_refs: list[str] = field(
        default_factory=list
    )
    role_families: list[str] = field(
        default_factory=list
    )

    evidence_count: int = 0
    independent_sources: int = 0
    sample_size: int = 0
    frequency: float = 0.0

    confidence: str = "low"
