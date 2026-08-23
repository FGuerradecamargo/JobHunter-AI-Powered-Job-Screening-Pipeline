import re

from models.candidate_profile import CandidateProfile
from models.job import Job
from models.job_profile import JobProfile


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
        "korean": [
            r"\bfluent korean\b",
            r"\bkorean required\b",
            r"\benglish and korean\b",
            r"\bkorean and english\b",
            r"\bkorean speaker\b",
            r"\bkorean-speaking\b",
            r"\bkorean/english bilingual\b",
            r"\benglish/korean bilingual\b",
        ],
    }

    STOPWORDS = {
        "and",
        "or",
        "the",
        "of",
        "for",
        "to",
        "in",
        "with",
        "operations",
        "operation",
        "specialist",
        "analyst",
        "associate",
    }

    def __init__(
        self,
        profile: CandidateProfile,
    ) -> None:
        self.profile = profile

        self.spoken_languages = {
            language.lower()
            for language in profile.spoken_languages
        }

        self.hard_constraints = {
            constraint.lower()
            for constraint in profile.hard_constraints
        }

        self.direction_roles = [
            profile.career_objective_title,
            *profile.target_roles,
            *profile.bridge_roles,
            *profile.target_role_families,
            *profile.bridge_role_families,
        ]

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
    def _tokens(
        cls,
        value: str,
    ) -> set[str]:
        tokens = set(
            re.findall(
                r"[a-z0-9+#]+",
                (value or "").lower(),
            )
        )

        return {
            token
            for token in tokens
            if (
                token not in cls.STOPWORDS
                and len(token) > 2
            )
        }

    def _role_matches_direction(
        self,
        job_profile: JobProfile,
    ) -> bool:
        role_text = " ".join(
            value
            for value in [
                job_profile.canonical_role,
                job_profile.role_family,
            ]
            if value
        ).lower()

        direction_text = " ".join(
            value
            for value in self.direction_roles
            if value
        ).lower()

        if not role_text.strip():
            return True

        # =============================================
        # 1. Clearly incompatible professional families
        # =============================================

        incompatible_terms = {
            "software engineering",
            "platform engineering",
            "site reliability engineering",
            "systems engineering",
            "machine learning",
            "data science",
            "cybersecurity",
            "information security",
            "security engineering",
            "controls engineering",
            "manufacturing engineering",
            "industrial engineering",
            "facilities engineering",
            "building automation",
            "mechanical engineering",
            "electrical engineering",
        }

        if any(
            term in role_text
            for term in incompatible_terms
        ):
            return False

        # =============================================
        # 2. Compatible professional regions
        # =============================================

        compatible_terms = {
            # Technical / IT support
            "technical support",
            "it support",
            "service desk",
            "help desk",
            "helpdesk",
            "application support",
            "product support",
            "support engineer",
            "support analyst",
            "customer support engineer",
            "end-user computing",
            "end user computing",
            "technical service",

            # Technical / support operations
            "technical operations",
            "technology operations",
            "it operations",
            "support operations",
            "service operations",
            "production support",
            "operations support",
            "incident management",
            "incident response",

            # Fraud / risk / financial crime
            "fraud",
            "financial crime",
            "financial crimes",
            "aml",
            "anti-money laundering",
            "sanctions",
            "risk operations",
            "fraud operations",
            "trust and safety",
            "investigation",
            "due diligence",
        }

        if any(
            term in role_text
            for term in compatible_terms
        ):
            return True

        # =============================================
        # 3. Fallback against candidate direction
        # =============================================

        job_tokens = self._tokens(role_text)

        if not job_tokens:
            return True

        for direction in self.direction_roles:
            if not direction:
                continue

            direction_tokens = self._tokens(
                direction
            )

            if not direction_tokens:
                continue

            overlap = (
                job_tokens
                & direction_tokens
            )

            if len(overlap) >= 2:
                return True

            normalized_direction = (
                direction.lower().strip()
            )

            if (
                normalized_direction
                and normalized_direction
                in role_text
            ):
                return True

        return False

    def _seniority_is_implausible(
        self,
        job_profile: JobProfile,
    ) -> bool:
        role_level = (
            job_profile.seniority
            or "unclear"
        ).lower()

        candidate_level = (
            self.profile.current_level
            or ""
        ).lower()

        if role_level in {
            "director",
            "executive",
        }:
            return (
                "director" not in candidate_level
                and "executive" not in candidate_level
            )

        return False

    def analyze(
        self,
        job: Job,
        job_profile: JobProfile | None = None,
    ) -> dict:
        title = (job.title or "").lower()
        description = (
            job.description
            or job.raw_text
            or ""
        ).lower()

        job_text = (
            f"{title}\n{description}"
        )

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
            and self._matches(
                job_text,
                self.NIGHT_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly includes night or overnight work."
            )

        if (
            self._has_constraint_signal("on-call")
            and self._matches(
                job_text,
                self.ON_CALL_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly includes blocking overnight on-call work."
            )

        if (
            self._has_constraint_signal("relocation")
            and self._matches(
                job_text,
                self.RELOCATION_PATTERNS,
            )
        ):
            reasons.append(
                "Role explicitly requires relocation."
            )

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
                    f"Mandatory {language.title()} "
                    "requirement is not present in "
                    "the candidate profile."
                )

        if job_profile is not None:
            if not self._role_matches_direction(
                job_profile
            ):
                reasons.append(
                    "Role is outside the candidate's "
                    "intended or bridge professional direction."
                )

            if self._seniority_is_implausible(
                job_profile
            ):
                reasons.append(
                    "Role seniority is clearly above "
                    "the candidate's plausible current range."
                )

        return {
            "rejected": bool(reasons),
            "reasons": reasons,
        }
