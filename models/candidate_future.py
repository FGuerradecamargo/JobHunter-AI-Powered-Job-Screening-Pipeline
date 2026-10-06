"""Declared professional direction, without inferred targets or market meaning."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateFuture:
    target_area: str | None = None
    target_role: str | None = None

    def __post_init__(self) -> None:
        for field in ("target_area", "target_role"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field} must be None or a nonblank string.")
