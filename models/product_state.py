from dataclasses import dataclass
from enum import Enum


class WorkPilotMode(str, Enum):
    SEARCH = "search"
    CAREER = "career"
    READ_ONLY = "read_only"


class HiredNextAction(str, Enum):
    KEEP_SEARCHING = "keep_searching"
    SWITCH_TO_CAREER = "switch_to_career"
    END_SUBSCRIPTION = "end_subscription"


@dataclass(frozen=True)
class CandidateProductState:
    candidate_id: str
    mode: WorkPilotMode = WorkPilotMode.SEARCH
    hired_job_id: str = ""
    subscription_end_requested: bool = False
    subscription_end_requested_at: str = ""
    updated_at: str = ""
    reason: str = ""
    source: str = ""

    @property
    def can_search(self) -> bool:
        return self.mode is WorkPilotMode.SEARCH

    @property
    def history_read_only(self) -> bool:
        return self.mode is WorkPilotMode.READ_ONLY


@dataclass(frozen=True)
class ProductStateTransition:
    candidate_id: str
    sequence: int
    before: CandidateProductState
    after: CandidateProductState
