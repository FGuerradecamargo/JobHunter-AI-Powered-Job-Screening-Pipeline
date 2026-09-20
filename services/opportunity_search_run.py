"""Session-local cooperative search, advanced once per authenticated UI rerun."""

from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4


@dataclass
class OpportunitySearchRun:
    authenticated_user_id: str
    active_user_id: str
    candidate_id: str
    context_signature: str
    target: int
    aggregate: dict
    scan_id: str = field(default_factory=lambda: "candidate_job_scan_" + uuid4().hex)
    status: str = "running"
    initialized: bool = False
    links_created: int = 0
    budget: object = None
    unavailable_job_ids: set[str] = field(default_factory=set)
    prepared_job_ids: list[str] = field(default_factory=list)

    @property
    def scope(self) -> tuple[str, str, str, str]:
        return (self.authenticated_user_id, self.active_user_id,
                self.candidate_id, self.context_signature)

    def stop(self, scope: tuple, scan_id: str) -> bool:
        if scope != self.scope or scan_id != self.scan_id:
            return False
        if self.status == "running":
            self.status = "stopped"
        return True

    def advance(self, scope: tuple, unit: Callable[[], bool]) -> None:
        """Complete at most one unit; True means more work remains.

        The unit must persist/merge its results before returning and must not
        call Streamlit (which can interrupt execution at an output boundary).
        A queued Stop click is handled on the next rerun, before another unit.
        """
        if scope != self.scope or self.status != "running":
            return
        try:
            more = unit()
        except Exception:
            # Keep already persisted results, and never retry implicitly.
            if self.status == "running":
                self.status = "failed"
            return
        if self.status == "running" and not more:
            self.status = "complete"
