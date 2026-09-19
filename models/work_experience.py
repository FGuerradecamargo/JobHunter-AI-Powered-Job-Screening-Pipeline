from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkExperience:
    id: str
    candidate_id: str

    company: str
    start_date: str
    end_date: Optional[str]

    career_story: str
    day_to_day_narrative: str
    confirmed_interview_answers: list = field(default_factory=list)
