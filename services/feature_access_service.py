from __future__ import annotations

from models.entitlement import Capability
from models.feature_access import FeatureAccessDecision
from models.membership_usage import MembershipUsageResult
from services.membership_usage_service import (
    MembershipUsageService,
)


def _to_decision(
    result: MembershipUsageResult,
) -> FeatureAccessDecision:

    return FeatureAccessDecision(
        capability=Capability(
            result.capability
        ),
        allowed=result.allowed,
        status=result.status,
        reason=result.reason,
        used=result.used,
        limit=result.limit,
        remaining=result.remaining,
        window=result.window,
        window_start=result.window_start,
        window_end=result.window_end,
        event_id=result.event_id,
    )


class FeatureAccessService:
    """
    Single commercial-access boundary for WorkPilot features.

    Features ask whether an action is available and, when the
    action represents metered usage, record consumption here.

    Candidate Product State remains a separate authority.
    """

    def __init__(
        self,
        *,
        usage_service=None,
    ) -> None:
        self.usage = (
            usage_service
            or MembershipUsageService()
        )

    def check(
        self,
        user_id: str,
        capability: Capability | str,
    ) -> FeatureAccessDecision:

        return _to_decision(
            self.usage.check(
                user_id,
                capability,
            )
        )

    def consume(
        self,
        user_id: str,
        capability: Capability | str,
        *,
        idempotency_key: str,
        amount: int = 1,
    ) -> FeatureAccessDecision:

        return _to_decision(
            self.usage.consume(
                user_id,
                capability,
                idempotency_key=(
                    idempotency_key
                ),
                amount=amount,
            )
        )
