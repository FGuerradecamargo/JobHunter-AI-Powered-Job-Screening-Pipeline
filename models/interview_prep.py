from dataclasses import dataclass, field


@dataclass
class InterviewPrep:
    what_the_company_needs: str = ""

    what_you_should_demonstrate: list[str] = field(
        default_factory=list
    )

    strongest_evidence: list[str] = field(
        default_factory=list
    )

    points_to_be_careful_with: list[str] = field(
        default_factory=list
    )

    likely_interview_topics: list[str] = field(
        default_factory=list
    )

    positioning: str = ""
