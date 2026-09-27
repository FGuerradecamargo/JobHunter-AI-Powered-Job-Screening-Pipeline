from dataclasses import dataclass


@dataclass(frozen=True)
class ApplicationLifecycleResult:
    status: str
    candidate_id: str
    job_id: str
    opportunity_state: str = ""
    applied_at: str | None = None
    error_code: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status in {
            "ready_to_apply",
            "applied",
            "already_applied",
            "user_rejected",
            "already_user_rejected",
        }
