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

    # Historical Market Position signals
    market_role_families: list[dict] = field(
        default_factory=list
    )
    market_strengths: list[dict] = field(
        default_factory=list
    )
    market_blockers: list[dict] = field(
        default_factory=list
    )
    market_fit_opportunities: list[dict] = field(
        default_factory=list
    )

    application_outcomes: list[dict] = field(
        default_factory=list
    )
