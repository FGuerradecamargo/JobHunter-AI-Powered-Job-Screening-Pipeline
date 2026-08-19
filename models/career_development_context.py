from dataclasses import dataclass, field


@dataclass
class CareerDevelopmentContext:
    candidate_id: str

    career_objective_title: str = ""
    career_objective_description: str = ""

    career_updates: list[str] = field(
        default_factory=list
    )

    analyzed_jobs_count: int = 0
    applied_jobs_count: int = 0
    interview_process_count: int = 0
    rejected_before_interview_count: int = 0
    rejected_after_interview_count: int = 0
    offers_count: int = 0

    recurring_development_gaps: list[dict] = field(
        default_factory=list
    )

    recurring_structural_gaps: list[dict] = field(
        default_factory=list
    )

    recurring_requirements_met: list[dict] = field(
        default_factory=list
    )

    application_outcomes: list[dict] = field(
        default_factory=list
    )
