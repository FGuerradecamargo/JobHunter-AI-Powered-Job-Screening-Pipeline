from dataclasses import dataclass, field


@dataclass
class CandidateOnboarding:
    candidate_id: str

    # Legacy compatibility fields remain until the onboarding UI migrates.
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

    # V4 candidate-authored source state, not interpreted Profile state.
    country: str = ""
    city: str = ""
    priority_declaration: str = ""

    def __post_init__(self):
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("candidate_id must be nonblank.")
        for value in (self.country, self.city, self.priority_declaration):
            if not isinstance(value, str):
                raise ValueError("V4 source text must be a string.")
        if not isinstance(self.spoken_languages, list) or any(
            not isinstance(value, str) or not value.strip() for value in self.spoken_languages
        ):
            raise ValueError("spoken_languages must contain explicit nonblank strings.")
