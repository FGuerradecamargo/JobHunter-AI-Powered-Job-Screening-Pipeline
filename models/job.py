from dataclasses import dataclass


# Representa uma vaga dentro do JobHunter.
@dataclass
class Job:
    id: str
    raw_text: str
    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    remote: bool | None = None
    salary: str | None = None
    easy_apply: bool = False
    score: float | None = None
    description: str | None = None
    reasons: list[str] | None = None
    classification: str | None = None