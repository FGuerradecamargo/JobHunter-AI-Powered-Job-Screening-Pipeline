"""Candidate-owned skill assessments, independent of employment and storage."""
from dataclasses import dataclass

from models.professional_ontology import Skill, SkillLevel


@dataclass(frozen=True)
class ProfessionalFactRef:
    """Reference exclusively to a Past ProfessionalFact, never a Present value.

    Existence must be checked where Past is available. This value neither loads
    evidence nor asserts that an arbitrary identifier has already been resolved.
    """

    fact_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, str) or not self.fact_id.strip():
            raise ValueError("fact_id must be a nonblank string.")


@dataclass(frozen=True)
class CandidateSkill:
    """An identified skill with assessed proficiency and immediate Past refs.

    Identity within a candidate's Present is the canonical skill.id.
    UNKNOWN retains the skill; only its proficiency is unknown.
    """

    skill: Skill
    level: SkillLevel
    evidence_refs: tuple[ProfessionalFactRef, ...]

    def __post_init__(self) -> None:
        if type(self.skill) is not Skill:
            raise TypeError("skill must be a canonical Skill.")
        if not isinstance(self.level, SkillLevel):
            raise TypeError("level must be a SkillLevel.")
        if not isinstance(self.evidence_refs, tuple) or any(
            type(ref) is not ProfessionalFactRef for ref in self.evidence_refs
        ):
            raise TypeError("evidence_refs must be a tuple of ProfessionalFactRef values.")
        if not self.evidence_refs:
            raise ValueError("A candidate skill requires Past fact evidence.")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("Duplicate fact references.")


@dataclass(frozen=True)
class CandidatePresent:
    skills: tuple[CandidateSkill, ...] = ()
    country: str | None = None
    city: str | None = None
    languages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("country", "city"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be None or a nonblank string.")
        if not isinstance(self.languages, tuple):
            raise TypeError("languages must be a tuple.")
        if any(not isinstance(value, str) or not value.strip() for value in self.languages):
            raise ValueError("Every language must be a nonblank string.")
        if len(set(self.languages)) != len(self.languages):
            raise ValueError("Duplicate language values.")
        if not isinstance(self.skills, tuple) or any(type(item) is not CandidateSkill for item in self.skills):
            raise TypeError("skills must be a tuple of CandidateSkill values.")
        if len({item.skill.id for item in self.skills}) != len(self.skills):
            raise ValueError("Duplicate candidate skill identities.")
