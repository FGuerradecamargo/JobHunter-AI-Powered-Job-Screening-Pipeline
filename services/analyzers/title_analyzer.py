import re


class TitleAnalyzer:
    POSITIVE_RULES = {
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

    NEGATIVE_RULES = {
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
                    f"Title contains '{keyword}': {points:+d}"
                )

        return score, reasons

    def analyze(self, title: str | None) -> dict:
        normalized_title = (title or "").lower()

        positive_score, positive_reasons = self.apply_rules(
            normalized_title,
            self.POSITIVE_RULES,
        )

        negative_score, negative_reasons = self.apply_rules(
            normalized_title,
            self.NEGATIVE_RULES,
        )

        return {
            "score": positive_score + negative_score,
            "reasons": positive_reasons + negative_reasons,
        }


if __name__ == "__main__":
    analyzer = TitleAnalyzer()

    titles = [
        "Technical Support Engineer",
        "Senior Platform Support Engineer",
        "Senior Sales Operations Associate",
    ]

    for title in titles:
        result = analyzer.analyze(title)

        print(title)
        print(result)
        print("-" * 60)