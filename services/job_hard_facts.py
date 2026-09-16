from __future__ import annotations

import hashlib
import json

from models.job_profile import JobProfile
from models.profile_interpretation import HardJobFact, JobHardFacts


def build_job_hard_facts(
    profile: JobProfile,
    *,
    explicit_blockers: tuple[str, ...] = (),
) -> JobHardFacts:
    """Project existing parsed fields into explicit, source-related facts."""
    categories = (
        ("responsibility", profile.key_responsibilities),
        ("must_have_capability", profile.must_have_capabilities),
        ("must_have_experience", profile.must_have_experience),
        ("nice_to_have", profile.nice_to_have),
        ("tool", profile.tools_and_technologies),
        ("qualification", profile.required_qualifications),
        ("structural_requirement", profile.structural_requirements),
        ("work_condition", profile.work_conditions),
        ("important_detail", profile.important_details),
    )
    rows: list[tuple[str, str, bool]] = []
    for kind, values in categories:
        rows.extend((kind, " ".join(value.split()), False) for value in values if value.strip())
    rows.extend(("eligibility", " ".join(value.split()), True) for value in explicit_blockers if value.strip())
    facts = []
    for index, (kind, value, blocker) in enumerate(rows):
        digest = hashlib.sha256(f"{kind}\0{value}".casefold().encode("utf-8")).hexdigest()
        facts.append(HardJobFact(
            fact_id=f"job-fact-{digest}", kind=kind, value=value,
            source_ref=f"job:{profile.job_id}:parsed:{kind}:{index}", hard_blocker=blocker,
        ))
    payload = [
        {"kind": item.kind, "value": item.value, "hard_blocker": item.hard_blocker}
        for item in facts
    ]
    signature = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return JobHardFacts(profile.job_id, signature, tuple(facts))
