import re

from models.candidate_profile import CandidateProfile
from models.job import Job


class JobMatcher:
    """
    Cheap contextual pre-filter.

    Its job is not to decide whether the candidate
    should apply.

    It only decides whether there is enough connection
    between the opportunity, the candidate's current
    direction and their real evidence to justify sending
    the job to AI.
    """

    RELEVANT = "relevant"
    REVIEW = "review"
    NOT_RELEVANT = "not_relevant"

    MIN_RELEVANT_SCORE = 18
    MIN_REVIEW_SCORE = 1

    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "work",
        "role",
        "roles",
        "job",
        "career",
        "professional",
        "current",
        "move",
        "moving",
        "long",
        "term",
        "where",
        "that",
        "this",
        "more",
    }

    @classmethod
    def _normalize(
        cls,
        value: str | None,
    ) -> str:
        text = (value or "").lower()

        text = re.sub(
            r"[^a-z0-9+#./ -]+",
            " ",
            text,
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    @classmethod
    def _tokens(
        cls,
        value: str | None,
    ) -> set[str]:
        normalized = cls._normalize(value)

        return {
            token
            for token in normalized.split()
            if (
                len(token) >= 3
                and token not in cls.STOP_WORDS
            )
        }

    @classmethod
    def _phrase_match(
        cls,
        job_text: str,
        value: str,
    ) -> bool:
        normalized = cls._normalize(value)

        if len(normalized) < 3:
            return False

        return normalized in job_text

    @classmethod
    def _token_overlap(
        cls,
        job_tokens: set[str],
        value: str,
    ) -> set[str]:
        return (
            job_tokens
            & cls._tokens(value)
        )

    def analyze(
        self,
        job: Job,
        profile: CandidateProfile,
    ) -> dict:
        title = self._normalize(job.title)
        description = self._normalize(
            job.description
        )

        job_text = (
            f"{title}\n{description}"
        ).strip()

        job_tokens = self._tokens(job_text)

        score = 0
        reasons: list[str] = []

        direction_score = 0
        evidence_score = 0

        # -------------------------------------------------
        # 1. Explicit current career objective
        # -------------------------------------------------

        objective_text = " ".join(
            value
            for value in [
                profile.career_objective_title,
                profile.career_objective_description,
            ]
            if value
        )

        if objective_text:
            overlap = self._token_overlap(
                job_tokens,
                objective_text,
            )

            if overlap:
                points = min(
                    12,
                    len(overlap) * 3,
                )

                direction_score += points

                reasons.append(
                    "Career objective overlap: "
                    + ", ".join(
                        sorted(overlap)
                    )
                    + f" (+{points})"
                )

        # -------------------------------------------------
        # 2. Role direction
        # -------------------------------------------------

        directional_roles = list(
            dict.fromkeys(
                profile.target_roles
                + profile.bridge_roles
                + profile.target_role_families
                + profile.bridge_role_families
            )
        )

        for role in directional_roles:
            if not role:
                continue

            if self._phrase_match(
                title,
                role,
            ):
                direction_score += 20

                reasons.append(
                    f"Target/bridge role match: "
                    f"'{role}' (+20)"
                )

                continue

            overlap = self._token_overlap(
                self._tokens(title),
                role,
            )

            if overlap:
                points = min(
                    10,
                    len(overlap) * 5,
                )

                direction_score += points

                reasons.append(
                    "Target/bridge title overlap: "
                    + ", ".join(
                        sorted(overlap)
                    )
                    + f" (+{points})"
                )

        # -------------------------------------------------
        # 3. Real evidence
        # -------------------------------------------------

        evidence_values = list(
            dict.fromkeys(
                profile.proven_capabilities
                + profile.transferable_capabilities
                + profile.technical_tools
                + profile.domain_experience
                + profile.current_skills
            )
        )

        matched_evidence: set[str] = set()

        for value in evidence_values:
            if not value:
                continue

            if self._phrase_match(
                job_text,
                value,
            ):
                matched_evidence.add(value)

                continue

            overlap = self._token_overlap(
                job_tokens,
                value,
            )

            if overlap:
                matched_evidence.add(value)

        if matched_evidence:
            points = min(
                15,
                len(matched_evidence) * 3,
            )

            evidence_score += points

            preview = sorted(
                matched_evidence
            )[:5]

            reasons.append(
                "Candidate evidence overlap: "
                + ", ".join(preview)
                + f" (+{points})"
            )

        # -------------------------------------------------
        # 4. Competitive role evidence
        #
        # This can support relevance, but historical
        # evidence must never define direction by itself.
        # -------------------------------------------------

        competitive_matches: list[str] = []

        for role in (
            profile.competitive_role_families
            + profile.current_roles
        ):
            if (
                role
                and self._phrase_match(
                    title,
                    role,
                )
            ):
                competitive_matches.append(role)

        if competitive_matches:
            points = min(
                6,
                len(competitive_matches) * 3,
            )

            evidence_score += points

            reasons.append(
                "Competitive experience match: "
                + ", ".join(
                    competitive_matches[:3]
                )
                + f" (+{points})"
            )

        # -------------------------------------------------
        # Final contextual score
        # -------------------------------------------------

        score = (
            direction_score
            + evidence_score
        )

        return {
            "score": score,
            "direction_score": direction_score,
            "evidence_score": evidence_score,
            "reasons": reasons,
        }

    def classify(
        self,
        job: Job,
    ) -> str:
        if job.score is None:
            return self.NOT_RELEVANT

        if job.score >= self.MIN_RELEVANT_SCORE:
            return self.RELEVANT

        if job.score >= self.MIN_REVIEW_SCORE:
            return self.REVIEW

        return self.NOT_RELEVANT
