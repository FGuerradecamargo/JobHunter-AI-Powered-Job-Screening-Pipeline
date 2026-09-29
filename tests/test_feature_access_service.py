from dataclasses import replace

from models.entitlement import (
    Capability,
    EntitlementRule,
    UsageWindow,
)
from models.membership_usage import (
    MembershipUsageResult,
)
from services.feature_access_service import (
    FeatureAccessService,
)
from services.membership_entitlement_policy import (
    MembershipEntitlementPolicy,
)
from services.membership_usage_service import (
    MembershipUsageService,
)
from services.user_repository import UserRepository


class FakeUsageService:

    def __init__(
        self,
        result,
    ):
        self.result = result
        self.check_calls = []
        self.consume_calls = []

    def check(
        self,
        user_id,
        capability,
    ):
        self.check_calls.append(
            (
                user_id,
                capability,
            )
        )

        return self.result

    def consume(
        self,
        user_id,
        capability,
        *,
        idempotency_key,
        amount=1,
    ):
        self.consume_calls.append(
            (
                user_id,
                capability,
                idempotency_key,
                amount,
            )
        )

        return self.result


def result(
    *,
    allowed=True,
    status="available",
    capability=(
        Capability.OPPORTUNITY_SEARCH
    ),
    used=0,
    limit=None,
    remaining=None,
    reason="unmetered",
):
    return MembershipUsageResult(
        status=status,
        user_id="user-1",
        capability=capability.value,
        allowed=allowed,
        used=used,
        limit=limit,
        remaining=remaining,
        window="none",
        reason=reason,
    )


def test_feature_access_check_exposes_stable_decision():
    usage = FakeUsageService(
        result()
    )

    access = FeatureAccessService(
        usage_service=usage
    )

    decision = access.check(
        "user-1",
        Capability.OPPORTUNITY_SEARCH,
    )

    assert decision.allowed
    assert (
        decision.capability
        is Capability.OPPORTUNITY_SEARCH
    )
    assert decision.status == "available"

    assert usage.check_calls == [
        (
            "user-1",
            Capability.OPPORTUNITY_SEARCH,
        )
    ]


def test_feature_access_does_not_expose_plan():
    access = FeatureAccessService(
        usage_service=FakeUsageService(
            result()
        )
    )

    decision = access.check(
        "user-1",
        Capability.OPPORTUNITY_SEARCH,
    )

    assert not hasattr(
        decision,
        "plan_code",
    )


def test_feature_access_preserves_quota_information():
    usage = FakeUsageService(
        result(
            used=2,
            limit=5,
            remaining=3,
            reason="available",
        )
    )

    decision = FeatureAccessService(
        usage_service=usage
    ).check(
        "user-1",
        Capability.OPPORTUNITY_SEARCH,
    )

    assert decision.allowed
    assert decision.used == 2
    assert decision.limit == 5
    assert decision.remaining == 3


def test_feature_access_preserves_denial():
    usage = FakeUsageService(
        result(
            allowed=False,
            status="limit_reached",
            used=5,
            limit=5,
            remaining=0,
            reason="usage_limit_reached",
        )
    )

    decision = FeatureAccessService(
        usage_service=usage
    ).check(
        "user-1",
        Capability.OPPORTUNITY_SEARCH,
    )

    assert not decision.allowed
    assert (
        decision.reason
        == "usage_limit_reached"
    )
    assert decision.remaining == 0


def test_feature_access_consumption_uses_idempotency():
    usage = FakeUsageService(
        result(
            status="consumed",
            used=1,
            limit=3,
            remaining=2,
            reason="consumed",
        )
    )

    access = FeatureAccessService(
        usage_service=usage
    )

    decision = access.consume(
        "user-1",
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key="search-run-1",
        amount=1,
    )

    assert decision.allowed
    assert decision.status == "consumed"

    assert usage.consume_calls == [
        (
            "user-1",
            Capability.OPPORTUNITY_SEARCH,
            "search-run-1",
            1,
        )
    ]


def test_real_free_user_can_use_open_default_capability():
    user = UserRepository().create(
        email="feature-access@example.com",
        display_name="Feature Access",
    )

    decision = (
        FeatureAccessService()
        .check(
            user.id,
            Capability.OPPORTUNITY_SEARCH,
        )
    )

    assert decision.allowed
    assert decision.limit is None
    assert decision.remaining is None


def test_gateway_works_when_catalog_changes_without_feature_changes():
    user = UserRepository().create(
        email="limited-feature@example.com",
        display_name="Limited Feature",
    )

    policy = MembershipEntitlementPolicy(
        catalog={
            "free": {
                Capability.OPPORTUNITY_SEARCH:
                    EntitlementRule(
                        capability=(
                            Capability.OPPORTUNITY_SEARCH
                        ),
                        limit=1,
                        window=UsageWindow.WEEK,
                    ),
            }
        }
    )

    usage = MembershipUsageService(
        entitlement_policy=policy
    )

    access = FeatureAccessService(
        usage_service=usage
    )

    before = access.check(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
    )

    assert before.allowed
    assert before.remaining == 1

    consumed = access.consume(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key="real-search-1",
    )

    assert consumed.allowed
    assert consumed.remaining == 0

    after = access.check(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
    )

    assert not after.allowed
    assert after.remaining == 0
    assert (
        after.reason
        == "usage_limit_reached"
    )
