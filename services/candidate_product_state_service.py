from dataclasses import replace

from models.product_state import HiredNextAction, WorkPilotMode
from services.candidate_product_state_repository import CandidateProductStateRepository
from services.database import utc_now


class HiredTransitionService:
    """Explicit actions only. The caller must supply the authorized active candidate."""

    def __init__(self, repository=None, *, clock=utc_now):
        self.repository = repository or CandidateProductStateRepository()
        self.clock = clock

    def choose(self, *, candidate_id, job_id, action):
        action = HiredNextAction(action)

        def decide(connection, before):
            outcome = connection.execute(
                """SELECT final_status FROM candidate_application_outcomes
                   WHERE candidate_id = ? AND job_id = ?""", (candidate_id, job_id),
            ).fetchone()
            if not outcome or outcome["final_status"] != "accepted":
                raise ValueError("An accepted application for this candidate is required.")
            if action is HiredNextAction.END_SUBSCRIPTION:
                if before.subscription_end_requested:
                    return before
                now = self.clock()
                return replace(before, hired_job_id=job_id, subscription_end_requested=True,
                               subscription_end_requested_at=now, updated_at=now,
                               reason=action.value, source="explicit_user_action")
            mode = (WorkPilotMode.SEARCH if action is HiredNextAction.KEEP_SEARCHING
                    else WorkPilotMode.CAREER)
            return self._change_mode(before, mode, action.value, job_id)

        return self.repository.transition(candidate_id, decide)

    def return_to_search(self, *, candidate_id):
        return self.repository.transition(candidate_id, lambda connection, before:
            self._change_mode(before, WorkPilotMode.SEARCH, "return_to_search"))

    def _change_mode(self, before, mode, reason, job_id=None):
        if before.mode is WorkPilotMode.READ_ONLY:
            raise ValueError("Access must be restored before changing product mode.")
        if before.mode is mode and (job_id is None or before.hired_job_id == job_id):
            return before
        return replace(before, mode=mode, hired_job_id=job_id or before.hired_job_id,
                       updated_at=self.clock(), reason=reason, source="explicit_user_action")


class ConfirmedProductAccessService:
    """Trusted server integration boundary, NOT an endpoint or billing adapter.

    Call only after an authoritative access decision. A subscription-end request
    is not confirmation. No production caller is wired until such authority exists.
    """

    def __init__(self, repository=None, *, clock=utc_now):
        self.repository = repository or CandidateProductStateRepository()
        self.clock = clock

    def confirm_read_only(self, *, candidate_id, confirmation_ref):
        if not isinstance(confirmation_ref, str) or not confirmation_ref.strip():
            raise ValueError("An authoritative access confirmation reference is required.")

        def decide(connection, before):
            if before.mode is WorkPilotMode.READ_ONLY:
                return before
            return replace(before, mode=WorkPilotMode.READ_ONLY, updated_at=self.clock(),
                           reason="access_ended", source=confirmation_ref.strip())

        return self.repository.transition(candidate_id, decide)
