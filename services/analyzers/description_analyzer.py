import re


class DescriptionAnalyzer:
    MAX_POSITIVE_SCORE = 15

    POSITIVE_RULES = {
        "python": 10,
        "sql": 10,
        "linux": 10,
        "root cause": 15,
        "troubleshooting": 15,
        "incident management": 15,
        "technical support": 15,
        "workflow automation": 15,
    }

    NEGATIVE_RULES = {
        "biopharmaceutical manufacturing": -40,
        "manufacturing engineering": -30,
        "lean manufacturing": -30,
        "mechanical engineering": -25,
        "assembly fixtures": -25,
    }

    @staticmethod
    def contains_keyword(text: str, keyword: str) -> bool:
        pattern = rf"\b{re.escape(keyword)}\b"
        return re.search(pattern, text) is not None

    def apply_rules(
        self,
        text: str,
        rules: dict[str, int],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        for keyword, points in rules.items():
            if self.contains_keyword(text, keyword):
                score += points
                reasons.append(
                    f"Description contains '{keyword}': {points:+d}"
                )

        return score, reasons

    def analyze(self, description: str | None) -> dict:
        normalized_description = (description or "").lower()

        positive_score, positive_reasons = self.apply_rules(
            normalized_description,
            self.POSITIVE_RULES,
        )

        negative_score, negative_reasons = self.apply_rules(
            normalized_description,
            self.NEGATIVE_RULES,
        )

        capped_positive_score = min(
            positive_score,
            self.MAX_POSITIVE_SCORE,
        )

        if positive_score > self.MAX_POSITIVE_SCORE:
            positive_reasons.append(
                "Description positive score capped at +15"
            )

        return {
            "score": capped_positive_score + negative_score,
            "reasons": positive_reasons + negative_reasons,
        }


if __name__ == "__main__":
    analyzer = DescriptionAnalyzer()

    descriptions = [
        "Automation Engineer in biopharmaceutical manufacturing.",
        (
            "Python, SQL and Linux support environment with "
            "troubleshooting and root cause analysis."
        ),
    ]

    for description in descriptions:
        result = analyzer.analyze(description)

        print(description)
        print(result)
        print("-" * 60)