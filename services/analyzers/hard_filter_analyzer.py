import re

from models.candidate_profile import CandidateProfile
from models.job import Job


class HardFilterAnalyzer:
    CLOSED_PATTERNS = [
        r"\bno longer accepting applications\b",
        r"\bapplications are closed\b",
        r"\bposition has been filled\b",
        r"\bjob is no longer available\b",
    ]

    NIGHT_PATTERNS = [
        r"\bnight shift\b",
        r"\bnight shifts\b",
        r"\bovernight\b",
        r"\bgraveyard shift\b",
        r"\bworking nights\b",
        r"\bnight rotation\b",
    ]

    ON_CALL_PATTERNS = [
        r"\bovernight on[- ]call\b",
        r"\b24/7 on[- ]call\b",
        r"\b24x7 on[- ]call\b",
        r"\bnight on[- ]call\b",
    ]

    RELOCATION_PATTERNS = [
        r"\bmust relocate\b",
        r"\brelocation required\b",
        r"\bmandatory relocation\b",
    ]

    REQUIRED_LANGUAGE_PATTERNS = {
        "german": [
            r"\bfluent german\b",
            r"\bgerman required\b",
            r"\benglish and german\b",
            r"\bgerman speaker\b",
            r"\bgerman-speaking\b",
        ],
        "french": [
            r"\bfluent french\b",
            r"\bfrench required\b",
            r"\benglish and french\b",
            r"\bfrench speaker\b",
            r"\bfrench-speaking\b",
        ],
        "dutch": [
            r"\bfluent dutch\b",
            r"\bdutch required\b",
            r"\benglish and dutch\b",
            r"\bdutch speaker\b",
            r"\bdutch-speaking\b",
        ],
        "spanish": [
            r"\bfluent spanish\b",
            r"\bspanish required\b",
            r"\benglish and spanish\b",
            r"\bspanish speaker\b",
            r"\bspanish-speaking\b",
        ],
        "italian": [
            r"\bfluent italian\b",
            r"\bitalian required\b",
            r"\benglish and italian\b",
            r"\bitalian speaker\b",
            r"\bitalian-speaking\b",
        ],
        "portuguese": [
            r"\bfluent portuguese\b",
            r"\bportuguese required\b",
            r"\benglish and portuguese\b",
            r"\bportuguese speaker\b",
            r"\bportuguese-speaking\b",
        ],
    }

    def __init__(
        self,
        profile: CandidateProfile,
    ) -> None:
        self.spoken_languages = {
            language.lower()
            for language in profile.spoken_languages
        }

        self.hard_constraints = {
            constraint.lower()
            for constraint in profile.hard_constraints
        }

    @staticmethod
    def _matches(
        text: str,
        patterns: list[str],
    ) -> bool:
        return any(
            re.search(pattern, text)
            for pattern in patterns
        )

    def _has_constraint_signal(
        self,
        phrase: str,
    ) -> bool:
        return any(
            phrase in constraint
            for constraint in self.hard_constraints
        )

    def analyze(
        self,
        job: Job,
    ) -> dict:
        title = (job.title or "").lower()
        description = (job.description or "").lower()
        job_text = f"{title}\n{description}"

        reasons: list[str] = []

        if self._matches(
            job_text,
            self.CLOSED_PATTERNS,
        ):
            reasons.append(
                "Job appears to be closed or unavailable."
            )

        if (
            self._has_constraint_signal(
                "night"
            )
            and self._matches(
                job_text,
                self.NIGHT_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly includes night or overnight work."
            )

        if (
            self._has_constraint_signal(
                "on-call"
            )
            and self._matches(
                job_text,
                self.ON_CALL_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly includes blocking overnight on-call work."
            )

        if (
            self._has_constraint_signal(
                "relocation"
            )
            and self._matches(
                job_text,
                self.RELOCATION_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly requires relocation."
            )

        if self._has_constraint_signal(
            "language"
        ):
            for language, patterns in (
                self.REQUIRED_LANGUAGE_PATTERNS.items()
            ):
                if (
                    language not in self.spoken_languages
                    and self._matches(
                        job_text,
                        patterns,
                    )
                ):
                    reasons.append(
                        f"Mandatory {language.title()} requirement "
                        "is not present in the candidate profile."
                    )

        return {
            "rejected": bool(reasons),
            "reasons": reasons,
        }
