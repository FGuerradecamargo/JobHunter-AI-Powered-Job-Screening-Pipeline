import re


class DescriptionAnalyzer:
    POSITIVE_RULES = {
        "python": 20,
    }


    NEGATIVE_RULES = {
        "biopharmaceutical manufacturing": -40,
    }

    @staticmethod
    def contains_keyword(text: str, keyword: str) -> bool:
        pattern = rf"\b{re.escape(keyword)}\b"
        return re.search(pattern, text) is not None

    def analyze(self, description: str | None) -> dict:
        normalized = (description or "").lower()

        score = 0
        reasons = []

        positive_score, positive_reasons = self.apply_rules(
            normalized,
            self.POSITIVE_RULES,
            "Description",
        )

        negative_score, negative_reasons = self.apply_rules(
            normalized,
            self.NEGATIVE_RULES,
            "Description",
        )

        score += positive_score
        score += negative_score

        reasons.extend(positive_reasons)
        reasons.extend(negative_reasons)

        return {
            "score": score,
            "reasons": reasons,
        }


# ← DAQUI PARA BAIXO NÃO HÁ MAIS INDENTAÇÃO

if __name__ == "__main__":
    analyzer = DescriptionAnalyzer()

    result = analyzer.analyze(
        "Automation Engineer in biopharmaceutical manufacturing."
    )

    print(result)