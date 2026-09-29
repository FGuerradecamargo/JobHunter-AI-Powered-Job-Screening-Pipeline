from dataclasses import replace
from datetime import (
    datetime,
    timezone,
)

from models.entitlement import (
    Capability,
    EntitlementRule,
    UsageWindow,
)
from models.membership import (
    MembershipStatus,
)
from services.database import (
    create_membership_usage_schema,
    get_connection,
)
from services.membership_entitlement_policy import (
    MembershipEntitlementPolicy,
)
from services.membership_repository import (
    MembershipRepository,
)
from services.membership_usage_service import (
    MembershipUsageService,
)
from services.user_repository import (
    UserRepository,
)


NOW = datetime(
    2026,
    9,
    29,
    8,
    0,
    tzinfo=timezone.utc,
)


def create_user():
    return UserRepository().create(
        email="usage@example.com",
        display_name="Usage",
    )


def limited_policy():
    return MembershipEntitlementPolicy(
        catalog={
            "free": {
                Capability.OPPORTUNITY_SEARCH:
                    EntitlementRule(
                        capability=(
                            Capability.OPPORTUNITY_SEARCH
                        ),
                        limit=3,
                        window=(
                            UsageWindow.WEEK
                        ),
                    ),
                Capability.PROFILE:
                    EntitlementRule(
                        capability=(
                            Capability.PROFILE
                        ),
                    ),
            }
        }
    )


def usage_service():
    return MembershipUsageService(
        entitlement_policy=(
            limited_policy()
        ),
        clock=lambda: NOW,
    )


def test_limited_capability_counts_and_stops_at_quota():
    user = create_user()
    usage = usage_service()

    initial = usage.check(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
    )

    assert initial.allowed
    assert initial.used == 0
    assert initial.remaining == 3

    first = usage.consume(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key="search-1",
    )

    assert first.status == "consumed"
    assert first.used == 1
    assert first.remaining == 2

    second = usage.consume(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key="search-2",
        amount=2,
    )

    assert second.status == "consumed"
    assert second.used == 3
    assert second.remaining == 0

    blocked = usage.consume(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key="search-3",
    )

    assert (
        blocked.status
        == "limit_reached"
    )

    assert not blocked.allowed
    assert blocked.used == 3
    assert blocked.remaining == 0


def test_same_operation_does_not_double_consume():
    user = create_user()
    usage = usage_service()

    first = usage.consume(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key="same-operation",
    )

    repeated = usage.consume(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key="same-operation",
    )

    assert (
        first.status
        == "consumed"
    )

    assert (
        repeated.status
        == "already_consumed"
    )

    assert (
        repeated.event_id
        == first.event_id
    )

    assert repeated.used == 1


def test_unlimited_capability_does_not_create_quota_event():
    user = create_user()
    usage = usage_service()

    result = usage.consume(
        user.id,
        Capability.PROFILE,
        idempotency_key="profile-1",
    )

    assert (
        result.status
        == "unmetered"
    )

    assert result.allowed
    assert result.limit is None
    assert result.remaining is None

    with get_connection() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) AS n
            FROM membership_usage_events
            WHERE user_id = ?
            """,
            (user.id,),
        ).fetchone()["n"]

    assert count == 0


def test_inactive_membership_cannot_consume():
    user = create_user()

    memberships = (
        MembershipRepository()
    )

    memberships.transition(
        user.id,
        lambda connection, before: replace(
            before,
            status=(
                MembershipStatus.CANCELED
            ),
            updated_at=(
                "2026-09-29T08:00:00+00:00"
            ),
            source="test",
        ),
    )

    usage = usage_service()

    result = usage.consume(
        user.id,
        Capability.OPPORTUNITY_SEARCH,
        idempotency_key=(
            "search-after-cancel"
        ),
    )

    assert result.status == "denied"
    assert not result.allowed

    assert (
        result.reason
        == "membership_inactive"
    )


def test_membership_period_fails_closed_without_period():
    user = create_user()

    policy = MembershipEntitlementPolicy(
        catalog={
            "free": {
                Capability.APPLICATION_PREPARATION:
                    EntitlementRule(
                        capability=(
                            Capability.APPLICATION_PREPARATION
                        ),
                        limit=1,
                        window=(
                            UsageWindow.MEMBERSHIP_PERIOD
                        ),
                    ),
            }
        }
    )

    usage = MembershipUsageService(
        entitlement_policy=policy,
        clock=lambda: NOW,
    )

    result = usage.check(
        user.id,
        Capability.APPLICATION_PREPARATION,
    )

    assert not result.allowed

    assert (
        result.reason
        == "usage_window_unavailable"
    )


def test_usage_schema_is_idempotent():
    with get_connection() as connection:
        create_membership_usage_schema(
            connection
        )

        create_membership_usage_schema(
            connection
        )

        columns = {
            row["name"]
            for row
            in connection.execute(
                """
                PRAGMA table_info(
                    membership_usage_events
                )
                """
            ).fetchall()
        }

    assert {
        "id",
        "user_id",
        "capability",
        "quantity",
        "idempotency_key",
        "window_start",
        "window_end",
        "occurred_at",
    } <= columns


def test_postgres_usage_table_is_server_only(
    monkeypatch,
):
    import services.database as database

    statements = []

    class Connection:
        def execute(
            self,
            sql,
        ):
            statements.append(
                sql
            )

    monkeypatch.setattr(
        database,
        "is_postgres",
        lambda: True,
    )

    create_membership_usage_schema(
        Connection()
    )

    assert (
        "ALTER TABLE membership_usage_events "
        "ENABLE ROW LEVEL SECURITY"
        in statements
    )

    assert (
        "REVOKE ALL ON TABLE "
        "membership_usage_events FROM PUBLIC"
        in statements
    )
