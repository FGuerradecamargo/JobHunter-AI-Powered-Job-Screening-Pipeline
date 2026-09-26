from __future__ import annotations

from dataclasses import dataclass
from models.company_profile import CompanyClaim


INTERVIEW_BRIEF_SCHEMA_VERSION = "interview-brief-v1"


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())


def _items(values) -> tuple[str, ...]:
    return tuple(
        _clean(value)
        for value in values or ()
        if _clean(value)
    )


@dataclass(frozen=True)
class InterviewerPublicContext:
    """
    Public professional context only.

    No personal investigation, protected characteristics, private contact
    details or inferred personality/decision style belong here.
    """
    name: str = ""
    role: str = ""
    current_role: str = ""
    professional_background: tuple[str, ...] = ()
    expertise_topics: tuple[str, ...] = ()
    likely_relationship_to_role: str = ""
    source_refs: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    public_only: bool = True

    def __post_init__(self) -> None:
        for name in (
            "name",
            "role",
            "current_role",
            "likely_relationship_to_role",
        ):
            object.__setattr__(
                self,
                name,
                _clean(getattr(self, name)),
            )
        for name in (
            "professional_background",
            "expertise_topics",
            "source_refs",
            "uncertainties",
        ):
            object.__setattr__(
                self,
                name,
                _items(getattr(self, name)),
            )
        if self.public_only is not True:
            raise ValueError(
                "Interviewer context must use public professional information only."
            )
        if not self.name and not self.role:
            raise ValueError(
                "Interviewer context needs a name or professional role."
            )
        if any(
            not ref.casefold().startswith(("https:", "web:"))
            for ref in self.source_refs
        ):
            raise ValueError(
                "Private sources cannot enter interviewer public context."
            )
        if (self.current_role or self.professional_background or self.expertise_topics
                or self.likely_relationship_to_role) and not self.source_refs:
            raise ValueError("Professional research context requires public provenance.")


@dataclass(frozen=True)
class InterviewBriefArea:
    topic: str
    guidance: str
    evidence_refs: tuple[str, ...] = ()
    caution: str = ""


@dataclass(frozen=True)
class InterviewBrief:
    candidate_id: str
    job_id: str
    interview_id: str
    round_sequence: int
    scheduled_at: str
    base_preparation_signature: str
    company_profile_version: int | None = None
    about_role: str = ""
    company_context: tuple[str, ...] = ()
    strongest_evidence: tuple[InterviewBriefArea, ...] = ()
    likely_areas: tuple[InterviewBriefArea, ...] = ()
    interviewer_contexts: tuple[InterviewerPublicContext, ...] = ()
    questions_to_ask: tuple[str, ...] = ()
    previous_round_feedback: tuple[str, ...] = ()
    next_stage_context: tuple[str, ...] = ()
    schema_version: str = INTERVIEW_BRIEF_SCHEMA_VERSION
    authority: str = "derived_interview_guidance"
    company_id: str = ""
    company_source_signature: str = ""
    company_claims: tuple[CompanyClaim, ...] = ()
    company_uncertainties: tuple[str, ...] = ()
    previous_round_refs: tuple[str, ...] = ()
    source_signature: str = ""

    def __post_init__(self) -> None:
        if (
            not _clean(self.candidate_id)
            or not _clean(self.job_id)
            or not _clean(self.interview_id)
            or self.round_sequence < 1
        ):
            raise ValueError("Interview brief scope is invalid.")
        if not _clean(self.base_preparation_signature):
            raise ValueError(
                "Interview brief requires a source preparation signature."
            )
        if self.authority != "derived_interview_guidance":
            raise ValueError("Interview brief authority is fixed.")
