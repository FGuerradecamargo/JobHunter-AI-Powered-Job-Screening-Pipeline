from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    PROFILE = "profile"
    APPLICATION_TRACKING = "application_tracking"
    IMPROVEMENTS = "improvements"
    OPPORTUNITY_SEARCH = "opportunity_search"
    APPLICATION_PREPARATION = "application_preparation"
    INTERVIEW_PREPARATION = "interview_preparation"


class UsageWindow(str, Enum):
    NONE = "none"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    MEMBERSHIP_PERIOD = "membership_period"


@dataclass(frozen=True)
class EntitlementRule:
    capability: Capability
    enabled: bool = True
    limit: int | None = None
    window: UsageWindow = UsageWindow.NONE

    def __post_init__(self) -> None:
        if (
            self.limit is not None
            and self.limit < 0
        ):
            raise ValueError(
                "Entitlement limit cannot be negative."
            )

        if (
            self.limit is None
            and self.window is not UsageWindow.NONE
        ):
            raise ValueError(
                "Unlimited entitlement cannot have a usage window."
            )

        if (
            self.limit is not None
            and self.window is UsageWindow.NONE
        ):
            raise ValueError(
                "Limited entitlement requires a usage window."
            )


@dataclass(frozen=True)
class EntitlementDecision:
    capability: Capability
    allowed: bool
    plan_code: str
    limit: int | None = None
    window: UsageWindow = UsageWindow.NONE
    reason: str = ""
