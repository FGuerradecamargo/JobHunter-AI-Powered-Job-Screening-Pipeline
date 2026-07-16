import re

from models.candidate_profile import CandidateProfile
from models.job import Job


class CandidateFitAnalyzer:
    CURRENT_SKILL_POINTS = 10
    BRIDGE_ROLE_POINTS = 20
    GROWTH_SKILL_POINTS = 5

    MAX_CURRENT_FIT_SCORE = 100
    MAX_GROWTH_VALUE_SCORE = 100

    @staticmethod
    def contains_keyword(
        text: str,
        keyword: str,
    ) -> bool:
        pattern = rf"\b{re.escape(keyword.lower())}\b"
        return re.search(pattern, text) is not None

    def analyze(
        self,
        job: Job,
        profile: CandidateProfile,
    ) -> dict:
        title = (job.title or "").lower()
        description = (job.description or "").lower()

        job_text = f"{title}\n{description}"

        current_fit_score = 0
        growth_value_score = 0

        current_fit_reasons = []
        growth_reasons = []

        for role in profile.bridge_roles:
            if self.contains_keyword(title, role):
                current_fit_score += self.BRIDGE_ROLE_POINTS
                current_fit_reasons.append(
                    f"Bridge role match: '{role}'"
                )

        for skill in profile.current_skills:
            if self.contains_keyword(job_text, skill):
                current_fit_score += self.CURRENT_SKILL_POINTS
                current_fit_reasons.append(
                    f"Current skill match: '{skill}'"
                )

        for skill in profile.growth_skills:
            if self.contains_keyword(job_text, skill):
                growth_value_score += self.GROWTH_SKILL_POINTS
                growth_reasons.append(
                    f"Growth skill opportunity: '{skill}'"
                )

        current_fit_score = min(
            current_fit_score,
            self.MAX_CURRENT_FIT_SCORE,
        )

        growth_value_score = min(
            growth_value_score,
            self.MAX_GROWTH_VALUE_SCORE,
        )

        return {
            "current_fit": current_fit_score,
            "growth_value": growth_value_score,
            "current_fit_reasons": current_fit_reasons,
            "growth_reasons": growth_reasons,
        }


if __name__ == "__main__":
    profile = CandidateProfile(
        bridge_roles=[
            "technical support engineer",
        ],
        current_skills=[
            "technical support",
            "troubleshooting",
            "root cause analysis",
        ],
        growth_skills=[
            "linux",
            "sql",
            "cloud",
        ],
    )

    job = Job(
        id="1",
        raw_text="Technical Support Engineer",
        url="https://example.com",
        title="Technical Support Engineer",
        description=(
            "Provide technical support, troubleshoot incidents, "
            "perform root cause analysis, and work with Linux "
            "and cloud platforms."
        ),
    )

    analyzer = CandidateFitAnalyzer()
    result = analyzer.analyze(job, profile)

    print(result)