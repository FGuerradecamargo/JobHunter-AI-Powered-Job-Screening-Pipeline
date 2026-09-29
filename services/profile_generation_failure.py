"""Safe internal failure categories for candidate-profile generation."""


_MESSAGES = {
    "no_professional_evidence": (
        "Confirmed candidate source evidence is not available."
    ),
    "invalid_json": (
        "Invalid structured candidate interpretation."
    ),
    "invalid_structured_output": (
        "Invalid structured candidate interpretation."
    ),
    "narrative_coverage_guard": (
        "Narrative onboarding cannot confirm complete finite-fact coverage."
    ),
    "capability_evidence_guard": (
        "Capability interpretation requires professional evidence from the source snapshot."
    ),
    "snapshot_persistence_failed": (
        "Candidate profile snapshot could not be persisted."
    ),
}


class ProfileGenerationFailure(ValueError):
    def __init__(
        self,
        code: str,
    ) -> None:
        if code not in _MESSAGES:
            raise ValueError(
                "Invalid profile generation failure code."
            )

        self.code = code

        super().__init__(
            _MESSAGES[code]
        )
