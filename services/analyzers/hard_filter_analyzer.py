import re

from models.candidate_profile import CandidateProfile
from models.job import Job
from models.job_profile import JobProfile


class HardFilterAnalyzer:
    """
    Legacy hard-filter boundary narrowed to V1 semantics.

    This class intentionally performs only objective, source-explicit checks that
    are representable safely in the current legacy CandidateProfile.

    Direction, seniority, transferable capability and "missing from profile"
    checks are relationship-analysis concerns and must not reject a job here.

    Structured language/licence/work-authorization absence checks move to the
    official CandidateProfileSnapshot path once its completeness metadata is
    wired into the search pipeline.
    """

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

    NIGHT_NEGATION_PATTERNS = [
        r"\bno night shifts?\b",
        r"\bnight shifts?\s+(?:are\s+)?not required\b",
        r"\bdoes not require\s+(?:night|overnight)\b",
        r"\bday shift only\b",
    ]

    ON_CALL_PATTERNS = [
        r"\bovernight on[- ]call\b",
        r"\b24/7 on[- ]call\b",
        r"\b24x7 on[- ]call\b",
        r"\bnight on[- ]call\b",
    ]

    ON_CALL_NEGATION_PATTERNS = [
        r"\bno (?:overnight )?on[- ]call\b",
        r"\bon[- ]call\s+(?:is\s+)?not required\b",
        r"\bwithout (?:overnight )?on[- ]call\b",
    ]

    RELOCATION_PATTERNS = [
        r"\bmust relocate\b",
        r"\brelocation required\b",
        r"\bmandatory relocation\b",
    ]

    RELOCATION_NEGATION_PATTERNS = [
        r"\bno relocation required\b",
        r"\brelocation (?:is )?not required\b",
        r"\bno need to relocate\b",
    ]

    def __init__(
        self,
        profile: CandidateProfile,
    ) -> None:
        self.profile = profile
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

    @classmethod
    def _explicit_requirement_present(
        cls,
        text: str,
        *,
        positive_patterns: list[str],
        negative_patterns: list[str],
    ) -> bool:
        # When the same topic appears in an explicit negation, the legacy text
        # layer is not authoritative enough to reject. V1 rule: when in doubt,
        # pass to relationship analysis.
        if cls._matches(text, negative_patterns):
            return False
        return cls._matches(text, positive_patterns)

    def analyze(
        self,
        job: Job,
        job_profile: JobProfile | None = None,
    ) -> dict:
        del job_profile  # kept in the public signature for migration compatibility

        title = (job.title or "").lower()
        description = (
            job.description
            or job.raw_text
            or ""
        ).lower()
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
            self._has_constraint_signal("night")
            and self._explicit_requirement_present(
                job_text,
                positive_patterns=self.NIGHT_PATTERNS,
                negative_patterns=self.NIGHT_NEGATION_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly includes night or overnight work."
            )

        if (
            self._has_constraint_signal("on-call")
            and self._explicit_requirement_present(
                job_text,
                positive_patterns=self.ON_CALL_PATTERNS,
                negative_patterns=self.ON_CALL_NEGATION_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly includes blocking overnight on-call work."
            )

        if (
            self._has_constraint_signal("relocation")
            and self._explicit_requirement_present(
                job_text,
                positive_patterns=self.RELOCATION_PATTERNS,
                negative_patterns=self.RELOCATION_NEGATION_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly requires relocation."
            )

        # Deliberately NOT hard-filtered here:
        # - professional direction/family
        # - seniority
        # - preferred years/degree/skills
        # - languages absent from a legacy, non-complete profile
        # - plausible transferable capability
        #
        # Those belong to Candidate ↔ Job analysis unless an authoritative
        # structured hard fact proves a non-substitutable incompatibility.

        return {
            "rejected": bool(reasons),
            "reasons": reasons,
        }
