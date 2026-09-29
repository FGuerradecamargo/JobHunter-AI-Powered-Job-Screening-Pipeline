from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from models.entitlement import (
    Capability,
    UsageWindow,
)
from models.membership import (
    MembershipState,
)
from models.membership_usage import (
    MembershipUsageResult,
)
from services.membership_entitlement_policy import (
    MembershipEntitlementPolicy,
)
from services.membership_repository import (
    MembershipRepository,
)
from services.membership_usage_repository import (
    MembershipUsageRepository,
)


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _parse_utc(
    value: str,
) -> datetime:

    parsed = datetime.fromisoformat(
        str(value or "").strip()
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _window_bounds(
    membership: MembershipState,
    window: UsageWindow,
    now: datetime,
) -> tuple[
    datetime,
    datetime,
] | None:

    now = now.astimezone(
        timezone.utc
    )

    if window is UsageWindow.DAY:
        start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        return (
            start,
            start + timedelta(days=1),
        )

    if window is UsageWindow.WEEK:
        day_start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        start = (
            day_start
            - timedelta(
                days=day_start.weekday()
            )
        )

        return (
            start,
            start + timedelta(days=7),
        )

    if window is UsageWindow.MONTH:
        start = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        if start.month == 12:
            end = start.replace(
                year=start.year + 1,
                month=1,
            )
        else:
            end = start.replace(
                month=start.month + 1,
            )

        return (
            start,
            end,
        )

    if (
        window
        is UsageWindow.MEMBERSHIP_PERIOD
    ):
        if (
            not membership.current_period_start
            or not membership.current_period_end
        ):
            return None

        start = _parse_utc(
            membership.current_period_start
        )

        end = _parse_utc(
            membership.current_period_end
        )

        if not (
            start <= now < end
        ):
            return None

        return (
            start,
            end,
        )

    return None


class MembershipUsageService:

    def __init__(
        self,
        *,
        membership_repository=None,
        entitlement_policy=None,
        usage_repository=None,
        clock=_utc_now,
    ) -> None:

        self.memberships = (
            membership_repository
            or MembershipRepository()
        )

        self.entitlements = (
            entitlement_policy
            or MembershipEntitlementPolicy()
        )

        self.usage = (
            usage_repository
            or MembershipUsageRepository()
        )

        self.clock = clock

    def check(
        self,
        user_id: str,
        capability: Capability | str,
    ) -> MembershipUsageResult:

        capability = Capability(
            capability
        )

        membership = (
            self.memberships.get(
                user_id
            )
        )

        entitlement = (
            self.entitlements.evaluate(
                membership,
                capability,
            )
        )

        if not entitlement.allowed:
            return MembershipUsageResult(
                status="denied",
                user_id=user_id,
                capability=(
                    capability.value
                ),
                allowed=False,
                used=0,
                limit=entitlement.limit,
                remaining=0,
                window=(
                    entitlement.window.value
                ),
                reason=(
                    entitlement.reason
                ),
            )

        if entitlement.limit is None:
            return MembershipUsageResult(
                status="available",
                user_id=user_id,
                capability=(
                    capability.value
                ),
                allowed=True,
                used=0,
                limit=None,
                remaining=None,
                window=(
                    UsageWindow.NONE.value
                ),
                reason="unmetered",
            )

        now = self.clock()

        bounds = _window_bounds(
            membership,
            entitlement.window,
            now,
        )

        if bounds is None:
            return MembershipUsageResult(
                status="denied",
                user_id=user_id,
                capability=(
                    capability.value
                ),
                allowed=False,
                used=0,
                limit=entitlement.limit,
                remaining=0,
                window=(
                    entitlement.window.value
                ),
                reason=(
                    "usage_window_unavailable"
                ),
            )

        start, end = bounds

        used = self.usage.count(
            user_id=user_id,
            capability=(
                capability.value
            ),
            window_start=(
                start.isoformat()
            ),
            window_end=(
                end.isoformat()
            ),
        )

        remaining = max(
            entitlement.limit - used,
            0,
        )

        return MembershipUsageResult(
            status=(
                "available"
                if remaining > 0
                else "limit_reached"
            ),
            user_id=user_id,
            capability=(
                capability.value
            ),
            allowed=(
                remaining > 0
            ),
            used=used,
            limit=entitlement.limit,
            remaining=remaining,
            window=(
                entitlement.window.value
            ),
            window_start=(
                start.isoformat()
            ),
            window_end=(
                end.isoformat()
            ),
            reason=(
                "available"
                if remaining > 0
                else "usage_limit_reached"
            ),
        )

    def consume(
        self,
        user_id: str,
        capability: Capability | str,
        *,
        idempotency_key: str,
        amount: int = 1,
    ) -> MembershipUsageResult:

        if amount <= 0:
            raise ValueError(
                "Usage amount must be positive."
            )

        idempotency_key = str(
            idempotency_key or ""
        ).strip()

        if not idempotency_key:
            raise ValueError(
                "Usage idempotency key is required."
            )

        capability = Capability(
            capability
        )

        membership = (
            self.memberships.get(
                user_id
            )
        )

        entitlement = (
            self.entitlements.evaluate(
                membership,
                capability,
            )
        )

        if not entitlement.allowed:
            return MembershipUsageResult(
                status="denied",
                user_id=user_id,
                capability=(
                    capability.value
                ),
                allowed=False,
                used=0,
                limit=entitlement.limit,
                remaining=0,
                window=(
                    entitlement.window.value
                ),
                reason=(
                    entitlement.reason
                ),
            )

        if entitlement.limit is None:
            return MembershipUsageResult(
                status="unmetered",
                user_id=user_id,
                capability=(
                    capability.value
                ),
                allowed=True,
                used=0,
                limit=None,
                remaining=None,
                window=(
                    UsageWindow.NONE.value
                ),
                reason="unmetered",
            )

        now = self.clock()

        bounds = _window_bounds(
            membership,
            entitlement.window,
            now,
        )

        if bounds is None:
            return MembershipUsageResult(
                status="denied",
                user_id=user_id,
                capability=(
                    capability.value
                ),
                allowed=False,
                used=0,
                limit=entitlement.limit,
                remaining=0,
                window=(
                    entitlement.window.value
                ),
                reason=(
                    "usage_window_unavailable"
                ),
            )

        start, end = bounds

        result = (
            self.usage.consume_limited(
                user_id=user_id,
                capability=(
                    capability.value
                ),
                amount=amount,
                limit=entitlement.limit,
                window_start=(
                    start.isoformat()
                ),
                window_end=(
                    end.isoformat()
                ),
                idempotency_key=(
                    idempotency_key
                ),
                occurred_at=(
                    now.isoformat()
                ),
            )
        )

        used = result["used"]

        remaining = max(
            entitlement.limit - used,
            0,
        )

        return MembershipUsageResult(
            status=result["status"],
            user_id=user_id,
            capability=(
                capability.value
            ),
            allowed=(
                result["status"]
                in {
                    "consumed",
                    "already_consumed",
                }
            ),
            used=used,
            limit=entitlement.limit,
            remaining=remaining,
            window=(
                entitlement.window.value
            ),
            window_start=(
                start.isoformat()
            ),
            window_end=(
                end.isoformat()
            ),
            event_id=result.get(
                "event_id",
                "",
            ),
            reason=(
                "usage_limit_reached"
                if (
                    result["status"]
                    == "limit_reached"
                )
                else result["status"]
            ),
        )
