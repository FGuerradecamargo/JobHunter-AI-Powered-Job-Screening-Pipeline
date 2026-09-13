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
            "applied",
            "already_applied",
            "user_rejected",
            "already_user_rejected",
        }
