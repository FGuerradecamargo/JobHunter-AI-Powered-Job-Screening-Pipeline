from models.job import Job
from services.analyzers.description_analyzer import DescriptionAnalyzer
from services.analyzers.title_analyzer import TitleAnalyzer


class JobMatcher:
    MIN_RELEVANT_SCORE = 30
    MIN_REVIEW_SCORE = 20

    RELEVANT = "relevant"
    REVIEW = "review"
    NOT_RELEVANT = "not_relevant"

    def __init__(self) -> None:
        self.title_analyzer = TitleAnalyzer()
        self.description_analyzer = DescriptionAnalyzer()

    def analyze(self, job: Job) -> dict:
        score = 0
        reasons = []

        title_analysis = self.title_analyzer.analyze(
            job.title
        )

        description_analysis = self.description_analyzer.analyze(
            job.description
        )

        title_score = title_analysis["score"]

        score += title_score
        score += description_analysis["score"]

        reasons.extend(title_analysis["reasons"])
        reasons.extend(description_analysis["reasons"])

        location = (job.location or "").lower()

        if title_score > 0 and score > 0 and "limerick" in location:
            score += 15
            reasons.append(
                "Relevant job located in Limerick: +15"
            )

        if title_score > 0 and score > 0 and job.remote is True:
            score += 10
            reasons.append(
                "Relevant job is remote: +10"
            )

        return {
            "score": score,
            "reasons": reasons,
        }

    def is_relevant(self, job: Job) -> bool:
        if job.score is None:
            return False

        return job.score >= self.MIN_RELEVANT_SCORE

    def classify(self, job: Job) -> str:
        if job.score is None:
            return self.NOT_RELEVANT

        if job.score >= self.MIN_RELEVANT_SCORE:
            return self.RELEVANT

        if job.score >= self.MIN_REVIEW_SCORE:
            return self.REVIEW

        return self.NOT_RELEVANT


if __name__ == "__main__":
    jobs = [
        Job(
            id="1",
            raw_text="Technical Support Engineer",
            url="https://example.com/1",
            title="Technical Support Engineer",
            location="Dublin, Ireland",
        ),
        Job(
            id="2",
            raw_text="Senior Platform Support Engineer",
            url="https://example.com/2",
            title="Senior Platform Support Engineer",
            location="Dublin, Ireland",
        ),
        Job(
            id="3",
            raw_text="Senior Sales Operations Associate",
            url="https://example.com/3",
            title="Senior Sales Operations Associate",
            location="Dublin, Ireland",
        ),
        Job(
            id="4",
            raw_text="Automation Engineer",
            url="https://example.com/4",
            title="Automation Engineer",
            location="Limerick, Ireland",
            description=(
                "Automation Engineer in "
                "biopharmaceutical manufacturing."
            ),
        ),
    ]

    matcher = JobMatcher()

    for job in jobs:
        result = matcher.analyze(job)
        job.score = result["score"]

        print(job.title)
        print(result)
        print(f"Classification: {matcher.classify(job)}")
        print("-" * 60)