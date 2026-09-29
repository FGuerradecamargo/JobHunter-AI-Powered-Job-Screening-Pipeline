import pytest

from services.candidate_product_state_repository import (
    CandidateProductStateRepository,
)


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(
        self,
        sql,
        params=(),
    ):
        self.calls.append(
            (
                " ".join(sql.split()),
                params,
            )
        )

        return Cursor(
            self.row
        )


def test_product_state_get_uses_one_query():
    connection = Connection(
        {
            "candidate_id": "candidate-a",
            "state_json": None,
        }
    )

    state = (
        CandidateProductStateRepository
        ._get(
            connection,
            "candidate-a",
        )
    )

    assert (
        state.candidate_id
        == "candidate-a"
    )

    assert len(
        connection.calls
    ) == 1

    sql, params = (
        connection.calls[0]
    )

    assert (
        "LEFT JOIN candidate_product_state"
        in sql
    )

    assert params == (
        "candidate-a",
    )


def test_product_state_get_missing_candidate_fails_closed():
    connection = Connection(
        None
    )

    with pytest.raises(
        ValueError,
        match="Candidate was not found",
    ):
        (
            CandidateProductStateRepository
            ._get(
                connection,
                "missing",
            )
        )

    assert len(
        connection.calls
    ) == 1


def test_blank_candidate_does_not_query_database():
    connection = Connection(
        None
    )

    with pytest.raises(
        ValueError,
        match="Candidate was not found",
    ):
        (
            CandidateProductStateRepository
            ._get(
                connection,
                "",
            )
        )

    assert connection.calls == []
