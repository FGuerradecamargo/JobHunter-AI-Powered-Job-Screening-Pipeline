from models.application_lifecycle import ApplicationLifecycleResult
from services.application_lifecycle_service import ApplicationLifecycleService


def handle_mark_applied_action(
    *,
    action_requested: bool,
    candidate_id: str,
    job_id: str,
    lifecycle_service: ApplicationLifecycleService,
) -> ApplicationLifecycleResult | None:
    if not action_requested:
        return None

    return lifecycle_service.mark_applied(candidate_id, job_id)


def handle_user_rejected_action(
    *,
    action_requested: bool,
    candidate_id: str,
    job_id: str,
    lifecycle_service: ApplicationLifecycleService,
) -> ApplicationLifecycleResult | None:
    if not action_requested:
        return None

    return lifecycle_service.mark_user_rejected(candidate_id, job_id)
