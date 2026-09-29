from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


DEFAULT_MEMBERSHIP_PLAN = "free"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class MembershipState:
    """
    User-scoped commercial access state.

    Prices, quotas, billing providers and Product State
    deliberately do not live here.
    """

    user_id: str
    plan_code: str = DEFAULT_MEMBERSHIP_PLAN
    status: MembershipStatus = MembershipStatus.ACTIVE

    trial_ends_at: str = ""
    current_period_start: str = ""
    current_period_end: str = ""
    grace_until: str = ""

    cancellation_requested_at: str = ""
    cancel_at_period_end: bool = False

    updated_at: str = ""
    source: str = "implicit_free"


@dataclass(frozen=True)
class MembershipTransition:
    user_id: str
    sequence: int
    before: MembershipState
    after: MembershipState
