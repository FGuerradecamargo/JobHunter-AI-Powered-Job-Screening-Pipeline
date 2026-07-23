import re

from models.candidate_profile import CandidateProfile
from models.job import Job


class HardFilterAnalyzer:
    NIGHT_PATTERNS = [
        r"\bnight shift\b",
        r"\bnight shifts\b",
        r"\bovernight\b",
        r"\bgraveyard shift\b",
        r"\bworking nights\b",
        r"\bnight rotation\b",
    ]

    CLOSED_PATTERNS = [
        r"\bno longer accepting applications\b",
        r"\bapplications are closed\b",
        r"\bposition has been filled\b",
        r"\bjob is no longer available\b",
    ]

    SPECIALIZED_TITLE_PATTERNS = {
        "advanced network engineering": [
            r"\bnetwork operations engineer\b",
            r"\bnetwork engineer\b",
            r"\bnetwork solutions engineer\b",
            r"\btac engineer\b",
        ],
        "DevOps or SRE": [
            r"\bsite reliability engineer\b",
            r"\bsre\b",
            r"\bdevops engineer\b",
            r"\bplatform engineer\b",
            r"\bcloud infrastructure engineer\b",
        ],
        "cybersecurity": [
            r"\bsecurity analyst\b",
            r"\bsecurity engineer\b",
            r"\bthreat detection\b",
            r"\bsoc analyst\b",
        ],
        "hardware or semiconductor engineering": [
            r"\bapplications engineer\b",
            r"\belectrical engineer\b",
            r"\bsemiconductor\b",
            r"\bhardware engineer\b",
        ],
        "pharmaceutical quality operations": [
            r"\bqms\b",
            r"\bquality systems\b",
            r"\bmanufacturing quality\b",
            r"\bvalidation engineer\b",
        ],
    }

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
    }

    SENIOR_TITLE_PATTERNS = [
        r"\bsenior\b",
        r"\bsr\.?\b",
        r"\bstaff\b",
        r"\bprincipal\b",
        r"\blead engineer\b",
        r"\barchitect\b",
    ]

    SPECIALIZED_REQUIREMENT_PATTERNS = [
        r"\b5\+ years\b",
        r"\b6\+ years\b",
        r"\b7\+ years\b",
        r"\b8\+ years\b",
        r"\bbgp\b",
        r"\bospf\b",
        r"\bmpls\b",
        r"\bvxlan\b",
        r"\bkubernetes\b",
        r"\bproduction aws\b",
        r"\bsite reliability\b",
        r"\bthreat modeling\b",
        r"\bsemiconductor\b",
    ]

    CLEAR_DOMAIN_MISMATCH_PATTERNS = {
        "AML and investor operations": [
            r"\baml investor operations\b",
            r"\binvestor operations\b",
            r"\banti-money laundering analyst\b",
            r"\baml analyst\b",
        ],
        "software or systems development": [
            r"\bsystems development engineer\b",
            r"\bsoftware development engineer\b",
            r"\bsoftware engineer\b",
        ],
    }

    CLEAR_LEADERSHIP_TITLE_PATTERNS = [
        r"\blead support engineer\b",
        r"\bincident service management lead\b",
        r"\btechnical support lead\b",
        r"\bsupport engineering lead\b",
    ]

    def __init__(
        self,
        profile: CandidateProfile,
    ) -> None:
        self.spoken_languages = {
            language.lower()
            for language in profile.spoken_languages
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

        if self._matches(
                job_text,
                self.NIGHT_PATTERNS,
        ):
            reasons.append(
                "Role explicitly includes night or overnight work."
            )

        for language, patterns in (
                self.REQUIRED_LANGUAGE_PATTERNS.items()
        ):
            if (
                    language not in self.spoken_languages
                    and self._matches(job_text, patterns)
            ):
                reasons.append(
                    f"Mandatory {language.title()} requirement "
                    "is not present in the candidate profile."
                )

        for domain, patterns in (
                self.SPECIALIZED_TITLE_PATTERNS.items()
        ):
            if self._matches(title, patterns):
                reasons.append(
                    "Role title indicates a specialized "
                    f"{domain} position."
                )
                break

        has_senior_title = self._matches(
            title,
            self.SENIOR_TITLE_PATTERNS,
        )

        has_specialized_requirements = self._matches(
            job_text,
            self.SPECIALIZED_REQUIREMENT_PATTERNS,
        )

        if (
                has_senior_title
                and has_specialized_requirements
        ):
            reasons.append(
                "Role combines seniority with specialized "
                "day-one technical requirements."
            )

        for domain, patterns in (
                self.CLEAR_DOMAIN_MISMATCH_PATTERNS.items()
        ):
            if self._matches(title, patterns):
                reasons.append(
                    "Role belongs to a clearly mismatched "
                    f"domain: {domain}."
                )
                break

        if self._matches(
                title,
                self.CLEAR_LEADERSHIP_TITLE_PATTERNS,
        ):
            reasons.append(
                "Role requires an established lead-level profile."
            )

        return {
            "rejected": bool(reasons),
            "reasons": reasons,
        }