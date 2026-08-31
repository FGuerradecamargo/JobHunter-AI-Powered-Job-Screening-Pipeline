from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from collections.abc import Iterable


@dataclass(frozen=True)
class FamilyAffinity:
    tier: str
    score: int
    matched_family: str | None = None
    matched_evidence: str | None = None


_TIER_BASE_SCORE = {
    "target": 300,
    "bridge": 200,
    "competitive": 100,
}


# Concept weights deliberately distinguish specific career
# families from broad words such as "operations".
#
# A broad Operations vacancy should not become a strong match
# merely because the candidate targets Technical Operations.
_CONCEPT_PATTERNS = {
    "technical_support": (
        4,
        (
            "technical support",
            "support engineer",
            "support engineering",
            "application support",
            "it support",
            "systems support",
            "technical customer support",
            "product support",
            "saas support",
        ),
    ),
    "technical_operations": (
        4,
        (
            "technical operations",
            "cloud operations",
            "production support",
            "incident response",
            "site reliability",
        ),
    ),
    "fraud_risk": (
        4,
        (
            "fraud",
            "risk operations",
            "risk analysis",
            "risk analytics",
            "fraud analysis",
            "fraud analytics",
            "trust and safety",
            "payments risk",
            "financial crime",
            "aml",
            "kyc",
        ),
    ),
    "customer_support": (
        3,
        (
            "customer support",
            "customer service",
            "customer operations",
            "customer success",
            "seller support",
            "merchant support",
            "support operations",
        ),
    ),
    "marketplace_operations": (
        3,
        (
            "marketplace operations",
            "marketplace ops",
        ),
    ),
    "manufacturing_operations": (
        3,
        (
            "manufacturing operations",
            "manufacturing ops",
        ),
    ),
    "product": (
        3,
        (
            "product management",
            "product operations",
        ),
    ),
    "analytics": (
        2,
        (
            "analytics",
            "analysis",
            "analyst",
            "analytical",
            "business intelligence",
            "data analysis",
        ),
    ),
    "coordination": (
        2,
        (
            "coordination",
            "coordinator",
        ),
    ),
    "operations": (
        1,
        (
            "operations",
            "operation",
            "operational",
            "service operations",
            "business operations",
            "process improvement",
        ),
    ),
    "engineering": (
        1,
        (
            "engineering",
            "engineer",
            "development",
            "developer",
        ),
    ),
}


_TOKEN_ALIASES = {
    "analysis": "analytics",
    "analyst": "analytics",
    "analytical": "analytics",
    "engineering": "engineer",
    "operations": "operation",
    "operational": "operation",
}


_STOPWORDS = {
    "and",
    "or",
    "of",
    "the",
    "a",
    "an",
    "for",
    "in",
    "to",
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )

    value = value.lower()
    value = value.replace("&", " and ")

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def _tokens(value: str) -> set[str]:
    normalized = _normalize(value)

    result: set[str] = set()

    for token in normalized.split():
        if token in _STOPWORDS:
            continue

        result.add(
            _TOKEN_ALIASES.get(
                token,
                token,
            )
        )

    return result


def _concepts(
    value: str,
) -> dict[str, int]:
    normalized = _normalize(value)

    found: dict[str, int] = {}

    for (
        concept,
        (
            weight,
            patterns,
        ),
    ) in _CONCEPT_PATTERNS.items():

        if any(
            pattern in normalized
            for pattern in patterns
        ):
            found[concept] = weight

    return found


def _match_strength(
    family: str,
    evidence: str,
) -> int:
    normalized_family = _normalize(
        family
    )

    normalized_evidence = _normalize(
        evidence
    )

    if (
        not normalized_family
        or not normalized_evidence
    ):
        return 0

    family_concepts = _concepts(
        normalized_family
    )

    evidence_concepts = _concepts(
        normalized_evidence
    )

    shared_concepts = (
        set(family_concepts)
        & set(evidence_concepts)
    )

    concept_strength = sum(
        min(
            family_concepts[concept],
            evidence_concepts[concept],
        )
        for concept in shared_concepts
    )

    family_tokens = _tokens(
        normalized_family
    )

    evidence_tokens = _tokens(
        normalized_evidence
    )

    shared_tokens = (
        family_tokens
        & evidence_tokens
    )

    strong_family_concepts = {
        concept
        for concept, weight
        in family_concepts.items()
        if weight >= 3
    }

    strong_shared_concepts = (
        strong_family_concepts
        & shared_concepts
    )

    exact_phrase = (
        normalized_family
        in normalized_evidence
    )

    # Specific families such as Technical Operations,
    # Fraud & Risk Analytics and Customer Operations
    # must match their specific domain concept.
    #
    # This prevents generic "Operations" or "Analytics"
    # vacancies from becoming false target matches.
    if strong_family_concepts:
        meaningful_match = bool(
            strong_shared_concepts
        ) or (
            exact_phrase
            and len(family_tokens) >= 2
        )

    else:
        meaningful_match = (
            concept_strength >= 2
            or len(shared_tokens) >= 2
            or (
                exact_phrase
                and len(family_tokens) >= 2
            )
        )

    if not meaningful_match:
        return 0

    exact_bonus = (
        5
        if exact_phrase
        else 0
    )

    token_bonus = min(
        len(shared_tokens),
        4,
    ) * 2

    return (
        concept_strength * 10
        + token_bonus
        + exact_bonus
    )


def _best_family_match(
    families: Iterable[str],
    evidence: Iterable[str],
) -> tuple[
    int,
    str | None,
    str | None,
]:
    best_strength = 0
    best_family = None
    best_evidence = None

    for family in families:
        normalized_family = str(
            family or ""
        ).strip()

        if not normalized_family:
            continue

        for item in evidence:
            normalized_item = str(
                item or ""
            ).strip()

            if not normalized_item:
                continue

            strength = _match_strength(
                normalized_family,
                normalized_item,
            )

            if strength > best_strength:
                best_strength = strength
                best_family = normalized_family
                best_evidence = normalized_item

    return (
        best_strength,
        best_family,
        best_evidence,
    )


def score_job_family_affinity(
    *,
    target_families: Iterable[str] = (),
    bridge_families: Iterable[str] = (),
    competitive_families: Iterable[str] = (),
    evidence: Iterable[str] = (),
) -> FamilyAffinity:
    """
    Rank career-family affinity without rejecting jobs.

    Priority:
        target
        bridge
        competitive
        fallback

    Family affinity changes discovery order only.
    A fallback job remains eligible for analysis.
    """

    evidence_items = tuple(
        str(item or "").strip()
        for item in evidence
        if str(item or "").strip()
    )

    tiers = (
        (
            "target",
            tuple(target_families),
        ),
        (
            "bridge",
            tuple(bridge_families),
        ),
        (
            "competitive",
            tuple(
                competitive_families
            ),
        ),
    )

    for tier, families in tiers:
        (
            strength,
            matched_family,
            matched_evidence,
        ) = _best_family_match(
            families,
            evidence_items,
        )

        if strength > 0:
            return FamilyAffinity(
                tier=tier,
                score=(
                    _TIER_BASE_SCORE[tier]
                    + strength
                ),
                matched_family=(
                    matched_family
                ),
                matched_evidence=(
                    matched_evidence
                ),
            )

    return FamilyAffinity(
        tier="fallback",
        score=0,
    )
