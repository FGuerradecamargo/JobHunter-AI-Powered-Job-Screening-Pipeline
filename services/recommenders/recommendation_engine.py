class RecommendationEngine:
    APPLY_NOW = "apply_now"
    CONSIDER = "consider"
    SAVE_FOR_LATER = "save_for_later"
    IGNORE = "ignore"

    APPLY_NOW_MIN_FIT = 70
    CONSIDER_MIN_FIT = 30
    SAVE_MIN_FIT = 20
    SAVE_MIN_GROWTH = 20
    HIGH_GROWTH_VALUE = 40

    def recommend(
        self,
        current_fit: int,
        growth_value: int,
    ) -> dict:
        if current_fit >= self.APPLY_NOW_MIN_FIT:
            return {
                "recommendation": self.APPLY_NOW,
                "message": (
                    "Excellent match for your current profile."
                ),
            }

        if current_fit >= self.CONSIDER_MIN_FIT:
            return {
                "recommendation": self.CONSIDER,
                "message": (
                    "Good bridge opportunity for your current profile."
                ),
            }

        if (
            current_fit >= self.SAVE_MIN_FIT
            and growth_value >= self.SAVE_MIN_GROWTH
        ):
            return {
                "recommendation": self.SAVE_FOR_LATER,
                "message": (
                    "Possible future opportunity with some current gaps."
                ),
            }

        if growth_value >= self.HIGH_GROWTH_VALUE:
            return {
                "recommendation": self.SAVE_FOR_LATER,
                "message": (
                    "Interesting long-term growth opportunity."
                ),
            }

        return {
            "recommendation": self.IGNORE,
            "message": (
                "Low alignment with your current profile and goals."
            ),
        }


if __name__ == "__main__":
    engine = RecommendationEngine()

    examples = [
        (80, 20),
        (55, 30),
        (30, 15),
        (20, 25),
        (10, 50),
        (10, 10),
    ]

    for current_fit, growth_value in examples:
        result = engine.recommend(
            current_fit,
            growth_value,
        )

        print(f"Current fit: {current_fit}")
        print(f"Growth value: {growth_value}")
        print(result)
        print("-" * 60)