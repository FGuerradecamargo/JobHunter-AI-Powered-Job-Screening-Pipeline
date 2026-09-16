from __future__ import annotations

from models.profile_interpretation import SourceEvidence
from services.career_memory_source_builder import CareerMemorySourceSnapshot


def build_candidate_profile_source_evidence(
    snapshot: CareerMemorySourceSnapshot,
) -> tuple[SourceEvidence, ...]:
    """Select source-backed experience records; derived memory/checkpoints are excluded."""
    candidate = snapshot.payload.get("candidate", {})
    experiences = candidate.get("professional_experiences", []) if isinstance(candidate, dict) else []
    result = []
    for item in experiences if isinstance(experiences, list) else []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_experience_id", "")).strip()
        if not source_id:
            continue
        parts = []
        for name in ("stated_role", "summary"):
            value = str(item.get(name, "")).strip()
            if value:
                parts.append(value)
        evidence = item.get("evidence", [])
        if isinstance(evidence, list):
            parts.extend(str(value).strip() for value in evidence if str(value).strip())
        result.append(SourceEvidence(
            ref=f"professional_experience:{source_id}",
            source_type="professional_experience",
            summary=" | ".join(parts),
        ))
    return tuple(sorted(result, key=lambda item: item.ref))
