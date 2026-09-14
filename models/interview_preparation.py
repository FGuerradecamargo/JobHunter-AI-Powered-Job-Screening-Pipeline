from dataclasses import dataclass, field


@dataclass(frozen=True)
class PreparationArea:
    topic: str
    source_type: str
    priority: str
    what_they_seek: str
    what_to_demonstrate: str
    example_direction: str
    emphasis: str = ""
    caution: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    gap_type: str = ""
    gap_text: str = ""


@dataclass(frozen=True)
class InterviewPreparation:
    candidate_id: str
    job_id: str
    analysis_id: str
    interview_context_signature: str
    interview_stage: str
    summary_guidance: str
    preparation_areas: list[PreparationArea] = field(default_factory=list)
    interview_instructions: list[str] = field(default_factory=list)
    questions_to_ask_the_company: list[str] = field(default_factory=list)
    rehearsal_prompts: list[str] = field(default_factory=list)
    source_signature: str = ""
    schema_version: str = "interview-preparation-v1"
    authority: str = "derived_interview_guidance"
