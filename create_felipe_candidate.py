from models.candidate import Candidate
from models.candidate_constraints import CandidateConstraints
from models.candidate_preferences import CandidatePreferences
from services.candidate_repository import CandidateRepository


def main() -> None:
    candidate = Candidate(
        id="felipe",
        name="Felipe Camargo dos Santos",
        current_role=(
            "Technical Operations, Product Support "
            "and Technical Investigations"
        ),
        current_level="mid",
        professional_summary=(
            "Technical Operations, Fraud Operations and "
            "Product Support professional with more than "
            "five years of experience across global "
            "technology platforms, complex investigations, "
            "payments, account integrity, quality assurance "
            "and operational improvement. Strong in root "
            "cause analysis, escalation handling, technical "
            "documentation, process improvement, Python "
            "automation and cross-functional collaboration."
        ),
        target_roles=[
            "Technical Support Engineer",
            "Product Support Engineer",
            "Technical Operations Specialist",
            "Technical Escalations Engineer",
            "Incident Management Analyst",
            "Support Automation Engineer",
        ],
        spoken_languages=[
            "english",
            "portuguese",
            "spanish",
        ],
        skills=[
            "technical support",
            "product support",
            "technical investigations",
            "root cause analysis",
            "escalation handling",
            "incident investigation",
            "fraud investigations",
            "payments",
            "chargebacks",
            "account integrity",
            "python",
            "selenium",
            "workflow automation",
            "process improvement",
            "technical documentation",
            "jira",
            "salesforce crm",
            "sql working knowledge",
            "rest api concepts",
            "cross-functional collaboration",
            "quality assurance",
        ],
        strengths=[
            "Complex case investigation",
            "Root cause analysis",
            "Escalation handling",
            "Structured decision-making",
            "Technical documentation",
            "Process improvement",
            "Python workflow automation",
            "Explaining complex issues clearly",
            "Working under operational pressure",
            "Supporting and training peers",
        ],
        development_areas=[
            "Professional SQL depth",
            "REST API troubleshooting",
            "Linux command-line confidence",
            "Cloud platform fundamentals",
            "Observability and monitoring",
            "B2B SaaS technical support",
            "Developer-facing support",
            "Production log analysis",
        ],
        preferences=CandidatePreferences(
            remote_allowed=True,
            hybrid_allowed=True,
            onsite_allowed=False,
            weekend_work_allowed=True,
            night_shift_allowed=False,
            on_call_allowed=False,
            customer_facing_preference="limited",
            phone_support_preference="limited",
            sales_adjacent_allowed=False,
            preferred_work_schedule="flexible",
        ),
        constraints=CandidateConstraints(
            relocation="conditional",
            minimum_salary=None,
            unsupported_languages_are_blocking=True,
            night_shift_is_blocking=True,
            mandatory_relocation_is_blocking=False,
            maximum_onsite_days_per_week=None,
        ),
    )

    repository = CandidateRepository()
    repository.save(candidate)

    print(
        "Candidate saved: "
        "data/candidates/felipe.json"
    )


if __name__ == "__main__":
    main()