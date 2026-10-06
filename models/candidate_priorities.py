"""Declared prioritization state, independent of rule interpretation/execution."""
from dataclasses import dataclass
from enum import Enum
from math import isfinite


class PriorityEffect(Enum):
    EXCLUDE = "exclude"
    DEPRIORITIZE = "deprioritize"
    PREFER = "prefer"


PriorityValue = str | int | float | bool


@dataclass(frozen=True)
class Priority:
    """A caller-identified rule; subject/operator/value are preserved, not inferred.

    Values are built-in immutable scalars only (finite floats). Their domain
    meaning and applicability are not evaluated by this state contract.
    """

    id: str
    subject: str
    operator: str
    value: PriorityValue
    effect: PriorityEffect

    def __post_init__(self) -> None:
        for field in ("id", "subject", "operator"):
            value = getattr(self, field)
            if type(value) is not str or not value.strip():
                raise ValueError(f"Priority {field} must be a nonblank string.")
        if type(self.value) not in (str, int, float, bool):
            raise TypeError("Priority value must be a built-in string, integer, float or boolean.")
        if type(self.value) is float and not isfinite(self.value):
            raise ValueError("Priority float value must be finite.")
        if not isinstance(self.effect, PriorityEffect):
            raise TypeError("Priority effect must be a PriorityEffect.")


@dataclass(frozen=True)
class CandidatePriorities:
    priorities: tuple[Priority, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.priorities, tuple) or any(
            type(item) is not Priority for item in self.priorities
        ):
            raise TypeError("priorities must be a tuple of Priority values.")
        if len({item.id for item in self.priorities}) != len(self.priorities):
            raise ValueError("Duplicate Priority identities.")
