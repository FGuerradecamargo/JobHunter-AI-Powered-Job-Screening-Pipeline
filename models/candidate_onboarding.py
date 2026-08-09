from dataclasses import dataclass, field


@dataclass
class CandidateOnboarding:
    candidate_id: str

    location: str = ""
    work_authorisation: str = ""

    spoken_languages: list[str] = field(
        default_factory=list
    )

    desired_next_work: str = ""
    enjoyed_work: str = ""
    avoid_work: str = ""
    development_interests: str = ""

    career_priorities: list[str] = field(
        default_factory=list
    )
