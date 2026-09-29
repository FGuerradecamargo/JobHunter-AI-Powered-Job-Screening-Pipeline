from dataclasses import replace

import pytest

from models.entitlement import (
    Capability,
    EntitlementRule,
    UsageWindow,
)
from models.membership import (
    MembershipState,
    MembershipStatus,
)
from services.membership_entitlement_policy import (
    DEFAULT_PLAN_CODES,
    MembershipEntitlementPolicy,
)


def membership(
    plan_code="free",
    status=MembershipStatus.ACTIVE,
):
    return MembershipState(
        user_id="user-1",
        plan_code=plan_code,
        status=status,
    )


def test_known_plans_support_core_capabilities_without_ui_coupling():
    policy = MembershipEntitlementPolicy()

    for plan_code in DEFAULT_PLAN_CODES:
        state = membership(
            plan_code=plan_code
        )

        for capability in Capability:
            decision = policy.evaluate(
                state,
                capability,
            )

            assert decision.allowed
            assert (
                decision.plan_code
                == plan_code
            )


def test_unknown_plan_fails_closed():
    decision = (
        MembershipEntitlementPolicy()
        .evaluate(
            membership(
                plan_code="unknown-plan"
            ),
            Capability.OPPORTUNITY_SEARCH,
        )
    )

    assert not decision.allowed
    assert (
        decision.reason
        == "unknown_plan"
    )


@pytest.mark.parametrize(
    "status",
    [
        MembershipStatus.PAST_DUE,
        MembershipStatus.CANCELED,
        MembershipStatus.EXPIRED,
    ],
)
def test_inactive_membership_does_not_grant_capabilities(
    status,
):
    decision = (
        MembershipEntitlementPolicy()
        .evaluate(
            membership(
                status=status
            ),
            Capability.PROFILE,
        )
    )

    assert not decision.allowed
    assert (
        decision.reason
        == "membership_inactive"
    )


def test_trialing_membership_can_receive_entitlements():
    decision = (
        MembershipEntitlementPolicy()
        .evaluate(
            membership(
                status=(
                    MembershipStatus.TRIALING
                )
            ),
            Capability.OPPORTUNITY_SEARCH,
        )
    )

    assert decision.allowed


def test_catalog_can_change_a_plan_without_changing_policy():
    catalog = {
        "free": {
            Capability.OPPORTUNITY_SEARCH:
                EntitlementRule(
                    capability=(
                        Capability.OPPORTUNITY_SEARCH
                    ),
                    enabled=True,
                    limit=3,
                    window=UsageWindow.WEEK,
                ),
            Capability.PROFILE:
                EntitlementRule(
                    capability=(
                        Capability.PROFILE
                    ),
                    enabled=True,
                ),
        }
    }

    policy = MembershipEntitlementPolicy(
        catalog=catalog
    )

    search = policy.evaluate(
        membership(),
        Capability.OPPORTUNITY_SEARCH,
    )

    assert search.allowed
    assert search.limit == 3
    assert search.window is UsageWindow.WEEK

    profile = policy.evaluate(
        membership(),
        Capability.PROFILE,
    )

    assert profile.allowed

    interview = policy.evaluate(
        membership(),
        Capability.INTERVIEW_PREPARATION,
    )

    assert not interview.allowed
    assert (
        interview.reason
        == "capability_not_included"
    )


def test_disabled_capability_is_denied():
    catalog = {
        "free": {
            Capability.APPLICATION_PREPARATION:
                EntitlementRule(
                    capability=(
                        Capability.APPLICATION_PREPARATION
                    ),
                    enabled=False,
                ),
        }
    }

    decision = (
        MembershipEntitlementPolicy(
            catalog=catalog
        )
        .evaluate(
            membership(),
            Capability.APPLICATION_PREPARATION,
        )
    )

    assert not decision.allowed


def test_limited_entitlement_requires_window():
    with pytest.raises(
        ValueError,
        match="usage window",
    ):
        EntitlementRule(
            capability=(
                Capability.OPPORTUNITY_SEARCH
            ),
            limit=3,
        )


def test_unlimited_entitlement_cannot_have_window():
    with pytest.raises(
        ValueError,
        match="Unlimited",
    ):
        EntitlementRule(
            capability=(
                Capability.OPPORTUNITY_SEARCH
            ),
            window=UsageWindow.WEEK,
        )


def test_membership_and_entitlements_remain_separate_objects():
    original = membership()

    custom = replace(
        original,
        plan_code="starter",
    )

    policy = MembershipEntitlementPolicy()

    assert (
        policy.evaluate(
            original,
            Capability.PROFILE,
        ).plan_code
        == "free"
    )

    assert (
        policy.evaluate(
            custom,
            Capability.PROFILE,
        ).plan_code
        == "starter"
    )

    assert original.plan_code == "free"
