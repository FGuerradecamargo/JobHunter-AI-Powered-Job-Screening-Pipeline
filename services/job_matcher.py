import re

from models.job import Job


class JobMatcher:
    MIN_RELEVANT_SCORE = 30

    POSITIVE_TITLE_RULES = {
        "technical": 20,
        "support": 20,
        "operations": 20,
        "incident": 20,
        "problem": 20,
        "escalation": 20,
        "investigation": 15,
        "investigations": 15,
        "automation": 15,
        "workflow": 15,
        "product": 15,
        "platform": 10,
        "systems": 10,
        "solutions": 10,
        "response": 10,
    }

    NEGATIVE_TITLE_RULES = {
        "sales": -30,
        "marketing": -30,
        "business development": -30,
        "account executive": -30,
        "recruitment": -25,
        "recruiter": -25,
        "retail": -25,
    }

    @staticmethod
    def contains_keyword(text: str, keyword: str) -> bool:
        pattern = rf"\b{re.escape(keyword)}\b"
        return re.search(pattern, text) is not None

    def analyze(self, job: Job) -> dict:
        score = 0
        reasons = []

        title = (job.title or "").lower()
        location = (job.location or "").lower()

        for keyword, points in self.POSITIVE_TITLE_RULES.items():
            if self.contains_keyword(title, keyword):
                score += points
                reasons.append(
                    f"Title contains '{keyword}': +{points}"
                )

        for keyword, points in self.NEGATIVE_TITLE_RULES.items():
            if self.contains_keyword(title, keyword):
                score += points
                reasons.append(
                    f"Title contains '{keyword}': {points}"
                )

        if score > 0 and "limerick" in location:
            score += 15
            reasons.append("Relevant job located in Limerick: +15")

        if score > 0 and job.remote is True:
            score += 10
            reasons.append("Job is remote: +10")

        return {
            "score": score,
            "reasons": reasons,
        }

    def is_relevant(self, job: Job) -> bool:
        if job.score is None:
            return False

        return job.score >= self.MIN_RELEVANT_SCORE


if __name__ == "__main__":
    jobs = [
        Job(
            id="4438647914",
            raw_text="Technical Support Engineer Intercom",
            url="https://www.linkedin.com/jobs/view/4438647914",
            title="Technical Support Engineer",
            company="Intercom",
            location="Dublin, County Dublin, Ireland",
        ),
        Job(
            id="4409993440",
            raw_text="Senior Platform Support Engineer Autodesk",
            url="https://www.linkedin.com/jobs/view/4409993440",
            title="Senior Platform Support Engineer",
            company="Autodesk",
            location="Dublin, County Dublin, Ireland",
        ),
        Job(
            id="4430436756",
            raw_text=(
                "Systems Engineer/linux Systems Engineer, "
                "Managed Operations"
            ),
            url="https://www.linkedin.com/jobs/view/4430436756",
            title=(
                "Systems Engineer/linux Systems Engineer, "
                "Managed Operations"
            ),
            company="Amazon Web Services",
            location="Dublin, County Dublin, Ireland",
        ),
        Job(
            id="4438323900",
            raw_text="Senior Sales Operations Associate Google",
            url="https://www.linkedin.com/jobs/view/4438323900",
            title="Senior Sales Operations Associate",
            company="Google",
            location="Dublin, County Dublin, Ireland",
        ),
    ]

    matcher = JobMatcher()

    for job in jobs:
        result = matcher.analyze(job)

        print(job.title)
        print(result)
        print("-" * 60)