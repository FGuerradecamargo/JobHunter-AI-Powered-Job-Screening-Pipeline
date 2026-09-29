from dataclasses import replace

import pytest

from models.membership import (
    DEFAULT_MEMBERSHIP_PLAN,
    MembershipState,
    MembershipStatus,
)
from services.database import (
    create_membership_schema,
    get_connection,
)
from services.membership_repository import (
    MembershipRepository,
)
from services.user_repository import (
    UserRepository,
)


def create_user(
    email="member@example.com",
):
    return UserRepository().create(
        email=email,
        display_name="Member",
    )


def test_existing_user_resolves_to_implicit_free_without_write():
    user = create_user()
    repository = MembershipRepository()

    state = repository.get(user.id)

    assert state == MembershipState(
        user_id=user.id
    )
    assert state.plan_code == DEFAULT_MEMBERSHIP_PLAN
    assert state.status is MembershipStatus.ACTIVE
    assert repository.history(user.id) == ()

    with get_connection() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) AS n
            FROM user_membership_state
            """
        ).fetchone()["n"]

    assert count == 0


def test_transition_persists_and_is_idempotent():
    user = create_user()
    repository = MembershipRepository()

    def activate_searching(connection, before):
        return replace(
            before,
            plan_code="searching",
            updated_at="2026-09-29T08:00:00+00:00",
            source="test",
        )

    state = repository.transition(
        user.id,
        activate_searching,
    )

    assert state.plan_code == "searching"
    assert repository.get(user.id) == state

    assert (
        repository.transition(
            user.id,
            activate_searching,
        )
        == state
    )

    history = repository.history(user.id)

    assert len(history) == 1
    assert history[0].before.plan_code == "free"
    assert history[0].after == state


def test_transition_cannot_change_owner():
    user = create_user()
    other = create_user("other@example.com")

    repository = MembershipRepository()

    with pytest.raises(
        ValueError,
        match="ownership",
    ):
        repository.transition(
            user.id,
            lambda connection, before: replace(
                before,
                user_id=other.id,
            ),
        )


def test_missing_user_fails_closed():
    with pytest.raises(
        ValueError,
        match="User was not found",
    ):
        MembershipRepository().get(
            "missing-user"
        )


def test_membership_cascades_with_user_deletion():
    user = create_user()
    repository = MembershipRepository()

    repository.transition(
        user.id,
        lambda connection, before: replace(
            before,
            plan_code="starter",
            updated_at="2026-09-29T08:05:00+00:00",
            source="test",
        ),
    )

    with get_connection() as connection:
        connection.execute(
            "DELETE FROM users WHERE id = ?",
            (user.id,),
        )

        state_count = connection.execute(
            """
            SELECT COUNT(*) AS n
            FROM user_membership_state
            WHERE user_id = ?
            """,
            (user.id,),
        ).fetchone()["n"]

        event_count = connection.execute(
            """
            SELECT COUNT(*) AS n
            FROM user_membership_state_events
            WHERE user_id = ?
            """,
            (user.id,),
        ).fetchone()["n"]

    assert state_count == 0
    assert event_count == 0


def test_schema_is_additive_and_idempotent():
    user = create_user()
    repository = MembershipRepository()

    state = repository.transition(
        user.id,
        lambda connection, before: replace(
            before,
            plan_code="career",
            updated_at="2026-09-29T08:10:00+00:00",
            source="test",
        ),
    )

    with get_connection() as connection:
        create_membership_schema(connection)
        create_membership_schema(connection)

    assert repository.get(user.id) == state
    assert len(repository.history(user.id)) == 1


def test_postgres_tables_are_server_only(
    monkeypatch,
):
    import services.database as database

    statements = []

    class Connection:
        def execute(self, sql):
            statements.append(sql)

    monkeypatch.setattr(
        database,
        "is_postgres",
        lambda: True,
    )

    create_membership_schema(
        Connection()
    )

    for table in (
        "user_membership_state",
        "user_membership_state_events",
    ):
        assert (
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
            in statements
        )

        assert (
            f"REVOKE ALL ON TABLE {table} FROM PUBLIC"
            in statements
        )
