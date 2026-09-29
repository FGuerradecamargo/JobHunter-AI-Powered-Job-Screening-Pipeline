from __future__ import annotations

from dataclasses import asdict
import json

from models.membership import (
    MembershipState,
    MembershipStatus,
    MembershipTransition,
)
from services.database import get_connection


def _decode(payload: str) -> MembershipState:
    values = json.loads(payload)
    values["status"] = MembershipStatus(values["status"])
    return MembershipState(**values)


class MembershipRepository:
    """
    Durable commercial-access authority.

    No billing-provider logic.
    No entitlement calculation.
    No Candidate Product State behavior.
    """

    def get(self, user_id: str) -> MembershipState:
        with get_connection() as connection:
            return self._get(connection, user_id)

    @staticmethod
    def _get(connection, user_id: str) -> MembershipState:
        user_id = str(user_id or "").strip()

        if (
            not user_id
            or not connection.execute(
                "SELECT id FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        ):
            raise ValueError("User was not found.")

        row = connection.execute(
            """
            SELECT state_json
            FROM user_membership_state
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return MembershipState(user_id=user_id)

        return _decode(row["state_json"])

    def transition(self, user_id: str, decide) -> MembershipState:
        user_id = str(user_id or "").strip()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET id = id
                WHERE id = ?
                """,
                (user_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError("User was not found.")

            before = self._get(connection, user_id)
            after = decide(connection, before)

            if not isinstance(after, MembershipState):
                raise TypeError(
                    "Membership transition must return MembershipState."
                )

            if after.user_id != user_id:
                raise ValueError(
                    "Membership ownership cannot change."
                )

            if not str(after.plan_code or "").strip():
                raise ValueError(
                    "Membership plan code cannot be empty."
                )

            MembershipStatus(after.status)

            if after == before:
                return before

            sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS n
                FROM user_membership_state_events
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()["n"]

            payload = json.dumps(
                asdict(after),
                sort_keys=True,
            )

            connection.execute(
                """
                INSERT INTO user_membership_state (
                    user_id,
                    state_json
                )
                VALUES (?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    state_json = excluded.state_json
                """,
                (user_id, payload),
            )

            connection.execute(
                """
                INSERT INTO user_membership_state_events (
                    user_id,
                    sequence,
                    before_json,
                    after_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    sequence,
                    json.dumps(
                        asdict(before),
                        sort_keys=True,
                    ),
                    payload,
                ),
            )

            return after

    def history(
        self,
        user_id: str,
    ) -> tuple[MembershipTransition, ...]:
        user_id = str(user_id or "").strip()

        with get_connection() as connection:
            self._get(connection, user_id)

            rows = connection.execute(
                """
                SELECT
                    sequence,
                    before_json,
                    after_json
                FROM user_membership_state_events
                WHERE user_id = ?
                ORDER BY sequence
                """,
                (user_id,),
            ).fetchall()

        return tuple(
            MembershipTransition(
                user_id=user_id,
                sequence=row["sequence"],
                before=_decode(row["before_json"]),
                after=_decode(row["after_json"]),
            )
            for row in rows
        )
