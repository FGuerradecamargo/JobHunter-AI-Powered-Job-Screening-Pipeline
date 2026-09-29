from __future__ import annotations

from dataclasses import dataclass

from models.entitlement import Capability


@dataclass(frozen=True)
class FeatureAccessDecision:
    """
    Stable feature-facing access contract.

    Product features do not need to know the user's plan,
    billing provider, entitlement catalog or usage storage.
    """

    capability: Capability
    allowed: bool
    status: str
    reason: str = ""

    used: int = 0
    limit: int | None = None
    remaining: int | None = None

    window: str = ""
    window_start: str = ""
    window_end: str = ""

    event_id: str = ""
