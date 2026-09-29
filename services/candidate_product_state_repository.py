"""Candidate-scoped state and append-only transition history; no billing side effects."""
from dataclasses import asdict
import json

from models.product_state import CandidateProductState, ProductStateTransition, WorkPilotMode
from services.database import get_connection


def _decode(payload):
    values = json.loads(payload)
    values["mode"] = WorkPilotMode(values["mode"])
    return CandidateProductState(**values)


class CandidateProductStateRepository:
    def get(self, candidate_id: str) -> CandidateProductState:
        with get_connection() as connection:
            return self._get(connection, candidate_id)

    @staticmethod
    def _get(
        connection,
        candidate_id,
    ):
        if not candidate_id:
            raise ValueError(
                "Candidate was not found."
            )

        row = connection.execute(
            """
            SELECT
                c.id AS candidate_id,
                s.state_json AS state_json
            FROM candidates c
            LEFT JOIN candidate_product_state s
              ON s.candidate_id = c.id
            WHERE c.id = ?
            """,
            (
                candidate_id,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                "Candidate was not found."
            )

        return (
            _decode(row["state_json"])
            if row["state_json"] is not None
            else CandidateProductState(
                candidate_id
            )
        )

    def transition(self, candidate_id, decide):
        with get_connection() as connection:
            # Lock a durable parent even before the first state row exists.
            connection.execute("UPDATE candidates SET id = id WHERE id = ?", (candidate_id,))
            before = self._get(connection, candidate_id)
            after = decide(connection, before)
            if after.candidate_id != candidate_id:
                raise ValueError("Product state ownership cannot change.")
            if after == before:
                return before
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS n FROM candidate_product_state_events WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()["n"]
            payload = json.dumps(asdict(after), sort_keys=True)
            connection.execute(
                """INSERT INTO candidate_product_state (candidate_id, state_json) VALUES (?, ?)
                   ON CONFLICT(candidate_id) DO UPDATE SET state_json = excluded.state_json""",
                (candidate_id, payload),
            )
            connection.execute(
                """INSERT INTO candidate_product_state_events
                   (candidate_id, sequence, before_json, after_json) VALUES (?, ?, ?, ?)""",
                (candidate_id, sequence, json.dumps(asdict(before), sort_keys=True), payload),
            )
            return after

    def history(self, candidate_id):
        with get_connection() as connection:
            self._get(connection, candidate_id)
            rows = connection.execute(
                "SELECT * FROM candidate_product_state_events WHERE candidate_id = ? ORDER BY sequence",
                (candidate_id,),
            ).fetchall()
        return tuple(ProductStateTransition(candidate_id, row["sequence"],
                                           _decode(row["before_json"]), _decode(row["after_json"])) for row in rows)
