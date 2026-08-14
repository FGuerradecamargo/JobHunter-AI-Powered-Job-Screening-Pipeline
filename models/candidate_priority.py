from dataclasses import dataclass


@dataclass
class CandidatePriority:
    text: str
    direction: str = "positive"
    active: bool = True
