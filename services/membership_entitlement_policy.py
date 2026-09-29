from __future__ import annotations

from collections.abc import Mapping

from models.entitlement import (
    Capability,
    EntitlementDecision,
    EntitlementRule,
    UsageWindow,
)
from models.membership import (
    MembershipState,
    MembershipStatus,
)


DEFAULT_PLAN_CODES = (
    "free",
    "starter",
    "career",
    "searching",
)


def _open_plan() -> dict[
    Capability,
    EntitlementRule,
]:
    """
    Phase 2 deliberately keeps known plans permissive.

    Commercial limits are configuration to be decided later.
    The entitlement engine already supports them.
    """
    return {
        capability: EntitlementRule(
            capability=capability,
            enabled=True,
        )
        for capability in Capability
    }


DEFAULT_ENTITLEMENT_CATALOG = {
    plan_code: _open_plan()
    for plan_code in DEFAULT_PLAN_CODES
}


class MembershipEntitlementPolicy:
    """
    Translates Membership state into capability decisions.

    Product pages should ask this policy what is allowed.
    They should not inspect plan names directly.
    """

    def __init__(
        self,
        catalog: Mapping[
            str,
            Mapping[
                Capability,
                EntitlementRule,
            ],
        ] | None = None,
    ) -> None:
        source = (
            catalog
            if catalog is not None
            else DEFAULT_ENTITLEMENT_CATALOG
        )

        self.catalog = {
            str(plan_code).strip().lower(): {
                Capability(capability): rule
                for capability, rule
                in rules.items()
            }
            for plan_code, rules
            in source.items()
        }

    def evaluate(
        self,
        membership: MembershipState,
        capability: Capability | str,
    ) -> EntitlementDecision:
        capability = Capability(
            capability
        )

        plan_code = str(
            membership.plan_code or ""
        ).strip().lower()

        plan = self.catalog.get(
            plan_code
        )

        if plan is None:
            return EntitlementDecision(
                capability=capability,
                allowed=False,
                plan_code=plan_code,
                reason="unknown_plan",
            )

        if membership.status not in {
            MembershipStatus.ACTIVE,
            MembershipStatus.TRIALING,
        }:
            return EntitlementDecision(
                capability=capability,
                allowed=False,
                plan_code=plan_code,
                reason="membership_inactive",
            )

        rule = plan.get(
            capability
        )

        if (
            rule is None
            or not rule.enabled
        ):
            return EntitlementDecision(
                capability=capability,
                allowed=False,
                plan_code=plan_code,
                reason="capability_not_included",
            )

        return EntitlementDecision(
            capability=capability,
            allowed=True,
            plan_code=plan_code,
            limit=rule.limit,
            window=rule.window,
            reason="allowed",
        )
