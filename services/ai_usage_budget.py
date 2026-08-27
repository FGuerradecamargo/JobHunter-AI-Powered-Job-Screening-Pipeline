from dataclasses import dataclass


@dataclass
class AIUsageBudget:
    """
    Candidate-job AI analysis allowance.

    remaining=None means unlimited.

    This intentionally does NOT meter shared JobProfile
    generation. It meters candidate-specific deep analysis.
    """

    remaining: int | None = None

    @classmethod
    def unlimited(cls) -> "AIUsageBudget":
        return cls(remaining=None)

    @property
    def exhausted(self) -> bool:
        return (
            self.remaining is not None
            and self.remaining <= 0
        )

    def consume(self, amount: int = 1) -> None:
        if amount <= 0:
            return

        if self.remaining is None:
            return

        self.remaining = max(
            0,
            self.remaining - amount,
        )
