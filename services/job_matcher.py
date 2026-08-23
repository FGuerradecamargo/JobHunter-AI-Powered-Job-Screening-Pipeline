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

    MIN_RELEVANT_SCORE = 22
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

    HIGH_SENIORITY_PHRASES = {
        "director",
        "head",
        "vice president",
        "vp",
        "principal",
        "staff",
    }

    SENIOR_PHRASES = {
        "senior",
        "lead",
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
        text: str,
        value: str,
    ) -> bool:
        normalized = cls._normalize(value)

        if len(normalized) < 3:
            return False

        return normalized in text

    @classmethod
    def _token_overlap(
        cls,
        text_tokens: set[str],
        value: str,
    ) -> set[str]:
        return (
            text_tokens
            & cls._tokens(value)
        )

    @classmethod
    def _seniority_penalty(
        cls,
        title: str,
        profile: CandidateProfile,
    ) -> tuple[int, str | None]:
        current_level = cls._normalize(
            getattr(
                profile,
                "current_level",
                "",
            )
        )

        candidate_is_senior = any(
            marker in current_level
            for marker in (
                "senior",
                "lead",
                "principal",
                "staff",
                "director",
                "head",
                "vice president",
                "vp",
            )
        )

        if candidate_is_senior:
            return 0, None

        for phrase in cls.HIGH_SENIORITY_PHRASES:
            if cls._phrase_match(
                title,
                phrase,
            ):
                return (
                    15,
                    f"High seniority mismatch: "
                    f"'{phrase}' (-15)",
                )

        for phrase in cls.SENIOR_PHRASES:
            if cls._phrase_match(
                title,
                phrase,
            ):
                return (
                    7,
                    f"Seniority mismatch: "
                    f"'{phrase}' (-7)",
                )

        return 0, None

    def analyze(
        self,
        job: Job,
        profile: CandidateProfile,
    ) -> dict:
        title = self._normalize(
            job.title
        )

        description = self._normalize(
            job.description
        )

        job_text = (
            f"{title}\n{description}"
        ).strip()

        title_tokens = self._tokens(
            title
        )

        job_tokens = self._tokens(
            job_text
        )

        reasons: list[str] = []

        direction_score = 0
        evidence_score = 0

        # -------------------------------------------------
        # 1. Explicit career objective
        #
        # A single broad word such as "process",
        # "customer", "analysis" or "technical" must not
        # create career direction by itself.
        #
        # We therefore require at least two title tokens
        # to overlap with the explicit objective title.
        # -------------------------------------------------

        objective_title = getattr(
            profile,
            "career_objective_title",
            "",
        ) or ""

        objective_tokens = self._tokens(
            objective_title
        )

        objective_overlap = (
            title_tokens
            & objective_tokens
        )

        if len(objective_overlap) >= 2:
            points = min(
                6,
                len(objective_overlap) * 3,
            )

            direction_score += points

            reasons.append(
                "Career objective title overlap: "
                + ", ".join(
                    sorted(
                        objective_overlap
                    )
                )
                + f" (+{points})"
            )

        # -------------------------------------------------
        # 2. Role direction
        #
        # Evaluate complete target/bridge concepts instead
        # of merging every role into one global token bag.
        #
        # Direction requires structure:
        # - a multi-word role phrase matches directly; or
        # - at least two tokens from the SAME multi-word
        #   role overlap with the job title.
        #
        # A generic single token such as "engineering",
        # "customer", "risk" or "automation" can no longer
        # create direction on its own.
        # -------------------------------------------------

        directional_roles = list(
            dict.fromkeys(
                (
                    profile.target_roles
                    + profile.bridge_roles
                    + profile.target_role_families
                    + profile.bridge_role_families
                )
            )
        )

        matched_role_tokens: set[str] = set()
        exact_role_matches: list[str] = []

        for role in directional_roles:
            if not role:
                continue

            role_tokens = self._tokens(
                role
            )

            # Single-word role concepts are too broad
            # to establish direction automatically.
            if len(role_tokens) < 2:
                continue

            if self._phrase_match(
                title,
                role,
            ):
                exact_role_matches.append(
                    role
                )

                matched_role_tokens.update(
                    role_tokens
                )

                continue

            overlap = (
                title_tokens
                & role_tokens
            )

            if len(overlap) >= 2:
                matched_role_tokens.update(
                    overlap
                )

        if matched_role_tokens:
            points = min(
                10,
                len(matched_role_tokens) * 5,
            )

            direction_score += points

            reasons.append(
                "Target/bridge direction overlap: "
                + ", ".join(
                    sorted(
                        matched_role_tokens
                    )
                )
                + f" (+{points})"
            )

        if exact_role_matches:
            best_match = sorted(
                exact_role_matches,
                key=len,
                reverse=True,
            )[0]

            direction_score += 10

            reasons.append(
                "Exact target/bridge role match: "
                f"'{best_match}' (+10)"
            )

        # -------------------------------------------------
        # 3. Real candidate evidence
        #
        # One generic shared word is no longer enough
        # for a multi-word capability to count.
        # -------------------------------------------------

        evidence_values = list(
            dict.fromkeys(
                (
                    profile.proven_capabilities
                    + profile.transferable_capabilities
                    + profile.technical_tools
                    + profile.domain_experience
                    + profile.current_skills
                )
            )
        )

        matched_evidence: set[str] = set()

        for value in evidence_values:
            if not value:
                continue

            value_tokens = self._tokens(
                value
            )

            if not value_tokens:
                continue

            if self._phrase_match(
                job_text,
                value,
            ):
                matched_evidence.add(
                    value
                )
                continue

            overlap = (
                job_tokens
                & value_tokens
            )

            if (
                len(value_tokens) == 1
                and len(overlap) == 1
            ):
                matched_evidence.add(
                    value
                )

            elif (
                len(value_tokens) >= 2
                and len(overlap) >= 2
            ):
                matched_evidence.add(
                    value
                )

        if matched_evidence:
            points = min(
                10,
                len(matched_evidence) * 2,
            )

            evidence_score += points

            preview = sorted(
                matched_evidence
            )[:5]

            reasons.append(
                "Candidate evidence overlap: "
                + ", ".join(
                    preview
                )
                + f" (+{points})"
            )

        # -------------------------------------------------
        # 4. Competitive/current role evidence
        #
        # Support only. It can never create direction.
        # -------------------------------------------------

        competitive_matches: list[str] = []

        competitive_roles = list(
            dict.fromkeys(
                (
                    profile.competitive_role_families
                    + profile.current_roles
                )
            )
        )

        for role in competitive_roles:
            if (
                role
                and self._phrase_match(
                    title,
                    role,
                )
            ):
                competitive_matches.append(
                    role
                )

        if competitive_matches:
            evidence_score += 3

            reasons.append(
                "Competitive experience match: "
                + ", ".join(
                    competitive_matches[:3]
                )
                + " (+3)"
            )

        # -------------------------------------------------
        # 5. Seniority mismatch
        # -------------------------------------------------

        penalty, penalty_reason = (
            self._seniority_penalty(
                title,
                profile,
            )
        )

        if penalty_reason:
            reasons.append(
                penalty_reason
            )

        # -------------------------------------------------
        # Final contextual score
        #
        # Historical evidence without current direction
        # must never make a job worth sending to AI.
        # -------------------------------------------------

        if direction_score <= 0:
            score = 0
        else:
            score = max(
                0,
                direction_score
                + evidence_score
                - penalty,
            )

        return {
            "score": score,
            "direction_score": direction_score,
            "evidence_score": evidence_score,
            "seniority_penalty": penalty,
            "reasons": reasons,
        }

    def classify(
        self,
        job: Job,
        matcher_analysis: dict | None = None,
    ) -> str:
        if job.score is None:
            return self.NOT_RELEVANT

        if job.score < self.MIN_REVIEW_SCORE:
            return self.NOT_RELEVANT

        evidence_score = None

        if matcher_analysis is not None:
            evidence_score = matcher_analysis.get(
                "evidence_score",
                0,
            )

        if job.score >= self.MIN_RELEVANT_SCORE:
            # Automatic AI analysis requires both
            # directional relevance and at least some
            # candidate evidence supporting the match.
            #
            # A strong title match alone remains REVIEW
            # instead of spending an AI call.
            if (
                evidence_score is None
                or evidence_score > 0
            ):
                return self.RELEVANT

        return self.REVIEW
