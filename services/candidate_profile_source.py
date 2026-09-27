from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

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


def load_confirmed_candidate_profile_input(candidate_id, repository):
    """V1 source boundary: confirmed user records, never generated Candidate text.

    The caller supplies the authorized candidate. Skips remain in the input
    record as unknowns but never create evidence refs or negative facts.
    """
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("Candidate identity is required.")
    experiences = repository.list_work_experiences(candidate_id)
    payload = {"source_schema": "confirmed-onboarding-v1", "experiences": []}
    sources = []
    for experience in sorted(experiences, key=lambda item: item.id):
        if experience.candidate_id != candidate_id:
            raise PermissionError("Experience belongs to another candidate.")
        answers = experience.confirmed_interview_answers
        record = {"experience_id": experience.id, "company": experience.company,
                  "start_date": experience.start_date, "end_date": experience.end_date,
                  "answers": [asdict(answer) for answer in answers]}
        if answers:
            for answer in answers:
                if not answer.skipped and answer.confirmed_text.strip():
                    ref = f"professional_experience:{experience.id}:{answer.interview_version}:{answer.question_id}"
                    sources.append(SourceEvidence(ref, "professional_experience", answer.confirmed_text))
        else:
            # Historical onboarding text is user-entered, unlike Candidate's
            # generated professional_experiences summaries.
            record["career_story"] = experience.career_story
            record["day_to_day_narrative"] = experience.day_to_day_narrative
            for field in ("career_story", "day_to_day_narrative"):
                text = getattr(experience, field)
                if text and text.strip():
                    sources.append(SourceEvidence(f"professional_experience:{experience.id}:{field}",
                                                  "professional_experience", text))
        payload["experiences"].append(record)
    sources = tuple(sorted(sources, key=lambda item: item.ref))
    encoded = json.dumps({"candidate_id": candidate_id, "payload": payload},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    signature = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return CareerMemorySourceSnapshot(candidate_id, payload, signature), sources
