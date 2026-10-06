"""Shared professional vocabulary, independent of its candidate or job usage."""
from dataclasses import dataclass
from enum import Enum


class SkillLevel(Enum):
    """Semantic levels, declared in progression order but deliberately not ordered.

    UNKNOWN is missing level knowledge, not absence of a skill or level zero.
    Serialize through ``value``; no numeric proficiency is implied.
    """

    UNKNOWN = "unknown"  # No reliable proficiency level is known.
    BASIC = "basic"  # Awareness or basic exposure.
    SUPPORTED = "supported"  # Working knowledge/use with support.
    INDEPENDENT = "independent"  # Independent practical use.
    ADVANCED = "advanced"  # Advanced use in complex contexts.
    EXPERT = "expert"  # Leads, designs, teaches, or demonstrates expert mastery.


@dataclass(frozen=True)
class Skill:
    """Canonical skill identity; category labels are shared, not consumer-specific.

    The caller supplies a stable id. Renaming a skill must not derive a new id.
    Proficiency, evidence and interpretation belong to the consuming contracts.
    """

    id: str
    name: str
    category: str
    subcategory: str | None = None

    def __post_init__(self) -> None:
        for field in ("id", "name", "category"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Skill {field} must be a nonblank string.")
        if self.subcategory is not None and (
            not isinstance(self.subcategory, str) or not self.subcategory.strip()
        ):
            raise ValueError("Skill subcategory must be None or a nonblank string.")
