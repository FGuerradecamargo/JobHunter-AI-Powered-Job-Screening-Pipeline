from dataclasses import dataclass, field


@dataclass(frozen=True)
class InterviewFeedback:
    candidate_id: str
    job_id: str
    interview_stage: str
    recruiter_feedback: str = ""
    candidate_notes: str = ""
    discussed_topics: list[str] = field(default_factory=list)
    difficult_topics: list[str] = field(default_factory=list)
    next_stage_instructions: str = ""
    created_at: str = ""
    updated_at: str = ""
