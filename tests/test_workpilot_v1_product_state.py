from concurrent.futures import ThreadPoolExecutor

import pytest

from models.product_state import HiredNextAction, WorkPilotMode
from services.candidate_product_state_repository import CandidateProductStateRepository
from services.candidate_product_state_service import HiredTransitionService, ConfirmedProductAccessService
from services.database import get_connection, create_product_state_schema
from tests.test_workpilot_v1_application_tracking import rounds


@pytest.fixture
def product(rounds):
    with get_connection() as con:
        con.execute("""INSERT INTO candidate_application_outcomes
            (candidate_id, job_id, final_status, created_at, updated_at)
            VALUES ('c', 'j', 'accepted', 'now', 'now')""")
    return HiredTransitionService(clock=lambda: "2026-09-27T12:00:00+00:00")


def choose(service, action):
    return service.choose(candidate_id="c", job_id="j", action=action)


def test_accepted_application_does_not_create_or_change_mode(product):
    assert product.repository.get("c").mode is WorkPilotMode.SEARCH
    assert product.repository.history("c") == ()
    with get_connection() as con:
        assert con.execute("SELECT COUNT(*) AS n FROM candidate_product_state").fetchone()["n"] == 0


@pytest.mark.parametrize("action,mode", [
    (HiredNextAction.KEEP_SEARCHING, WorkPilotMode.SEARCH),
    (HiredNextAction.SWITCH_TO_CAREER, WorkPilotMode.CAREER),
    (HiredNextAction.END_SUBSCRIPTION, WorkPilotMode.SEARCH),
])
def test_explicit_choices_persist_and_are_idempotent(product, action, mode):
    state = choose(product, action)
    assert state.mode is mode
    assert choose(product, action) == state
    assert CandidateProductStateRepository().get("c") == state
    history = product.repository.history("c")
    assert len(history) == 1
    assert history[0].after == state
    assert state.source == "explicit_user_action"


def test_career_returns_explicitly_to_search_preserving_pending_intent(product):
    choose(product, HiredNextAction.SWITCH_TO_CAREER)
    requested = choose(product, HiredNextAction.END_SUBSCRIPTION)
    assert requested.mode is WorkPilotMode.CAREER
    assert requested.subscription_end_requested
    assert requested.subscription_end_requested_at
    assert not requested.can_search
    state = product.return_to_search(candidate_id="c")
    assert state.mode is WorkPilotMode.SEARCH
    assert state.can_search
    assert state.subscription_end_requested
    assert product.return_to_search(candidate_id="c") == state
    assert len(product.repository.history("c")) == 3


def test_choices_require_own_accepted_application(product):
    with pytest.raises(ValueError, match="accepted"):
        product.choose(candidate_id="other", job_id="j", action=HiredNextAction.SWITCH_TO_CAREER)
    with pytest.raises(ValueError, match="accepted"):
        product.choose(candidate_id="c", job_id="missing", action=HiredNextAction.END_SUBSCRIPTION)
    assert product.repository.get("other").mode is WorkPilotMode.SEARCH
    assert product.repository.history("other") == ()


def test_concurrent_identical_requests_make_one_event(product):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: choose(product, HiredNextAction.END_SUBSCRIPTION), range(8)))
    assert all(state == results[0] for state in results)
    assert len(product.repository.history("c")) == 1


def test_access_confirmation_is_separate_and_user_cannot_override(product):
    choose(product, HiredNextAction.END_SUBSCRIPTION)
    access = ConfirmedProductAccessService(clock=lambda: "2026-09-28T12:00:00+00:00")
    with pytest.raises(ValueError):
        access.confirm_read_only(candidate_id="c", confirmation_ref="")
    state = access.confirm_read_only(candidate_id="c", confirmation_ref="access-decision:test-1")
    assert state.mode is WorkPilotMode.READ_ONLY
    assert state.history_read_only and not state.can_search
    assert access.confirm_read_only(candidate_id="c", confirmation_ref="access-decision:test-1") == state
    with pytest.raises(ValueError, match="restored"):
        product.return_to_search(candidate_id="c")
    with pytest.raises(ValueError, match="restored"):
        choose(product, HiredNextAction.SWITCH_TO_CAREER)
    assert choose(product, HiredNextAction.END_SUBSCRIPTION) == state
    assert product.repository.get("other").mode is WorkPilotMode.SEARCH


def snapshot_non_product_tables():
    with get_connection() as con:
        tables = [row["name"] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'candidate_product_state%'"
        ).fetchall()]
        return {table: [tuple(row) for row in con.execute(f'SELECT * FROM "{table}"').fetchall()]
                for table in tables}


def test_modes_and_end_request_preserve_all_history_and_evidence(product):
    before = snapshot_non_product_tables()
    choose(product, HiredNextAction.SWITCH_TO_CAREER)
    choose(product, HiredNextAction.END_SUBSCRIPTION)
    ConfirmedProductAccessService().confirm_read_only(candidate_id="c", confirmation_ref="access-decision:test")
    assert snapshot_non_product_tables() == before
    with get_connection() as con:
        assert con.execute("SELECT final_status FROM candidate_application_outcomes").fetchone()["final_status"] == "accepted"


def test_schema_is_additive_idempotent_and_preserves_state(product):
    state = choose(product, HiredNextAction.END_SUBSCRIPTION)
    with get_connection() as con:
        create_product_state_schema(con)
        create_product_state_schema(con)
    assert product.repository.get("c") == state
    assert len(product.repository.history("c")) == 1


def test_postgres_schema_secures_both_tables(monkeypatch):
    import services.database as database
    statements = []
    class Connection:
        def execute(self, sql):
            statements.append(sql)
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    create_product_state_schema(Connection())
    for table in ("candidate_product_state", "candidate_product_state_events"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"REVOKE ALL ON TABLE {table} FROM PUBLIC" in statements


def test_missing_candidate_and_invalid_action_fail_closed(product):
    with pytest.raises(ValueError):
        product.repository.get("missing")
    with pytest.raises(ValueError):
        choose(product, "cancelled_by_provider")
    assert product.repository.history("c") == ()
